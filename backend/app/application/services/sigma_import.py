"""
Filling in from Sigma what the facials cannot know.

The equipment owns the identifier, the name and the face. Where somebody lives and
which documents they carry exist only in Sigma, and until now had to be typed by
hand — for everyone, again after every change.

What this does not do is decide who is who. It matches on identifier *and* name, the
rule ADR 0010 settled on after devices enrolled separately were found reusing
numbers: identifier 2 named three different people. A name that does not match is
reported rather than written, because the alternative is putting one resident's
address and CPF onto another's record.
"""

from collections import defaultdict
from datetime import datetime

from app.application.ports.resident_repository import ResidentRepository
from app.application.services.resident_search import fold
from app.core.logger import logger
from app.domain.entities.automation import ImportStatus
from app.domain.entities.sigma import (
    SIGMA_PHOTO_PREFIX,
    SigmaDweller,
    SigmaImportReport,
    SigmaVisitorReport,
)
from app.sigma.client import SigmaClient, SigmaUnavailable

DEVICE_NAME_LIMIT = 32
"""
Onde a facial corta o nome.

Medido no cadastro real: nenhum nome passa de 32 caracteres, e cinco param
exatamente nele — "Peterson Henrique Freitas do Nas" é o Nascimento cortado. Sem
saber disso, quatro pessoas do Sigma não casariam com ninguém.
"""


def match_name(sigma_name: str, candidates: set[str]) -> str | None:
    """The local name for this person, or ``None`` when it cannot be said which.

    Two differences are expected and safe to look past. Sigma writes accents and the
    facials often do not, so the comparison folds them. And the equipment truncates
    at 32 characters, so a local name that stops exactly there and prefixes the Sigma
    one is that same name, cut.

    Neither loosens what ADR 0010 protects. That rule exists because devices enrolled
    separately reuse *identifiers* for different people — identifier 2 names three of
    them — and the name is what tells those apart. "nk" and "naldo" still fail here.
    The prefix is only accepted at the truncation limit, so a genuinely short name
    like "Ana" never swallows "Ana Maria".
    """
    folded = fold(sigma_name)
    exatos = [c for c in candidates if fold(c) == folded]
    if len(exatos) == 1:
        return exatos[0]
    if exatos:
        return None

    truncados = [
        c for c in candidates
        if len(c) >= DEVICE_NAME_LIMIT and folded.startswith(fold(c))
    ]
    return truncados[0] if len(truncados) == 1 else None


class SigmaImportService:
    def __init__(self, residents: ResidentRepository) -> None:
        self._residents = residents

    async def run(self, client: SigmaClient, account_id: int) -> SigmaImportReport:
        visitantes = await client.visitors(account_id)
        pessoas = await client.dwellers(account_id) + visitantes
        logger.info("Sigma devolveu {} pessoa(s) na conta {}.", len(pessoas), account_id)

        # Lido uma vez: são centenas de cadastros, e consultar por pessoa faria uma
        # varredura do diretório inteiro para cada uma delas.
        por_identificador, com_foto = self._facial_directory()

        updated = photos = 0
        unmatched: list[str] = []
        situacao: dict[tuple[str, str], bool] = {}
        for pessoa in pessoas:
            changes = _changes_of(pessoa)
            local = match_name(pessoa.name, por_identificador.get(pessoa.enrollment, set()))
            if local is not None:
                # Anotado para todos que casaram, tenham ou não outro dado a gravar: o
                # que o porteiro precisa saber é justamente quem o Sigma desativou.
                situacao[(pessoa.enrollment, local)] = pessoa.enabled

            precisa_foto = pessoa.sigma_id is not None
            if not changes and not precisa_foto:
                # Está no Sigma sem nada que nos sirva: gravar isto seria escrever
                # nada e ainda contar como atualização.
                continue

            if local is None:
                # Desativado e fora das faciais é o esperado — quem saiu e já foi
                # removido dos equipamentos. Listá-los encheria o aviso de ruído.
                # O visitante fora das faciais também não é falha: ele entra no pMoni
                # pela etapa dos visitantes, logo abaixo.
                if changes and pessoa.enabled and not pessoa.visitor:
                    unmatched.append(f"{pessoa.name} (ID {pessoa.enrollment})")
                continue
            # Gravado sob o nome que está no cadastro, não sob o do Sigma: é por ele
            # que as linhas daquela pessoa são encontradas.
            if changes and self._residents.set_person_details(pessoa.enrollment, local, changes):
                updated += 1
            if precisa_foto and (pessoa.enrollment, local) not in com_foto:
                if await self._fill_photo(client, account_id, pessoa, local):
                    photos += 1

        inactive = sum(1 for enabled in situacao.values() if not enabled)
        self._residents.set_active(situacao)
        visitors = await self._keep_visitors(client, account_id, visitantes, por_identificador)
        return SigmaImportReport(
            read=len(pessoas), updated=updated, unmatched=unmatched, photos=photos,
            inactive=inactive, visitors=visitors,
        )

    async def run_visitors(self, client: SigmaClient, account_id: int) -> SigmaVisitorReport:
        """Only the visitors step: cheap enough to run on every periodic check.

        Two requests to Sigma, plus a photo for each visitor seen for the first time.
        The full import reads every resident and asks for hundreds of photos, which
        is right once a night and far too much every few minutes.
        """
        visitantes = await client.visitors(account_id)
        por_identificador, _ = self._facial_directory()
        return await self._keep_visitors(client, account_id, visitantes, por_identificador)

    def _facial_directory(self) -> tuple[dict[str, set[str]], set[tuple[str, str]]]:
        """Names per identifier on the facials, and who already has a picture.

        Visitors kept from Sigma alone are left out of the names: they are what the
        import is matching *against* the facials, not part of them.
        """
        por_identificador: dict[str, set[str]] = defaultdict(set)
        com_foto: set[tuple[str, str]] = set()
        for enrollment in self._residents.list_directory():
            if enrollment.has_photo:
                com_foto.add((enrollment.employee_no, enrollment.name))
            if enrollment.device_id is not None:
                por_identificador[enrollment.employee_no].add(enrollment.name)
        return por_identificador, com_foto

    async def _keep_visitors(
        self,
        client: SigmaClient,
        account_id: int,
        visitantes: list[SigmaDweller],
        por_identificador: dict[str, set[str]],
    ) -> SigmaVisitorReport:
        """Bring into pMoni the visitors active in Sigma that no facial holds.

        The porter lets them in by hand and has to find them first — host unit,
        document, face — in the same search as the residents. One on a facial is
        left to that enrollment, so the same person never shows up twice; one
        disabled in Sigma is removed, since they no longer have anywhere to visit.
        """
        conhecidos = self._residents.sigma_visitors()
        manter: set[int] = set()
        created = updated = photos = 0
        for visitante in visitantes:
            if not visitante.enabled or visitante.sigma_id is None:
                continue
            nomes = por_identificador.get(visitante.enrollment, set()) if visitante.enrollment else set()
            if match_name(visitante.name, nomes) is not None:
                continue
            manter.add(visitante.sigma_id)
            # Só na primeira vez que aparece: perguntar de novo a cada verificação
            # por quem o Sigma não tem foto repetiria a mesma resposta o dia inteiro.
            photo = None
            if visitante.sigma_id not in conhecidos:
                photo = await self._photo_of(client, account_id, visitante)
                photos += 1 if photo is not None else 0
            if self._residents.save_sigma_visitor(visitante, photo=photo):
                created += 1
            else:
                updated += 1
        removed = self._residents.drop_sigma_visitors(manter)
        if created or removed:
            logger.info(
                "Visitantes do Sigma sem facial: {} novos, {} removidos, {} no total.",
                created, removed, len(manter),
            )
        return SigmaVisitorReport(created=created, updated=updated, removed=removed, photos=photos)

    async def _photo_of(
        self, client: SigmaClient, account_id: int, pessoa: SigmaDweller
    ) -> bytes | None:
        """The profile photo, or ``None`` — a photo failing never costs the import."""
        try:
            return await client.profile_photo(account_id, pessoa.sigma_id)
        except SigmaUnavailable as exc:
            logger.warning("Foto do Sigma indisponível para {}: {}", pessoa.name, exc)
            return None

    async def _fill_photo(
        self, client: SigmaClient, account_id: int, pessoa: SigmaDweller, local: str
    ) -> bool:
        """Give the Sigma profile photo to someone no facial kept a picture of.

        Visitors and people since disabled are the usual case: the equipment holds
        only their biometric template, and without this the porter sees initials
        where a face should be. One photo failing must not cost the rest of the
        import, so a failure here is logged and skipped.
        """
        photo = await self._photo_of(client, account_id, pessoa)
        if photo is None:
            return False
        return bool(
            self._residents.set_fallback_photo(
                pessoa.enrollment, local, photo,
                reference=f"{SIGMA_PHOTO_PREFIX}{pessoa.sigma_id}",
            )
        )


def _changes_of(pessoa: SigmaDweller) -> dict[str, str | None]:
    """Only what Sigma actually filled in.

    A field Sigma left empty is left alone here: it means Sigma does not know it, not
    that it should be erased. Blanking a CPF somebody typed by hand, because the
    Sigma record happens to be incomplete, would be losing data on an import.
    """
    candidatos = {
        "apartment": pessoa.apartment,
        "block": pessoa.block,
        "cpf": pessoa.cpf,
        "rg": pessoa.rg,
    }
    return {campo: valor for campo, valor in candidatos.items() if valor is not None}


def outcome_of(report: SigmaImportReport) -> tuple[ImportStatus, str]:
    """Turn the numbers into the line the operator reads on the screen."""
    resumo = f"{report.updated} de {report.read} pessoas atualizadas."
    if report.photos:
        resumo += f" {report.photos} foto(s) de perfil trazidas para quem não tinha."
    if report.inactive:
        resumo += f" {report.inactive} desativada(s) no Sigma e ainda nas faciais."
    if report.visitors is not None:
        resumo += f" {visitors_summary(report.visitors)}"
    if not report.unmatched:
        return ImportStatus.OK, resumo

    mostrados = ", ".join(report.unmatched[:3])
    resto = f" e mais {len(report.unmatched) - 3}" if len(report.unmatched) > 3 else ""
    detalhe = (
        f"{resumo} {len(report.unmatched)} não encontradas nas faciais "
        f"(nome diferente ou sem cadastro): {mostrados}{resto}."
    )
    # Nada casar quase sempre é a conta errada, e não um cadastro todo divergente.
    status = ImportStatus.FAILED if report.updated == 0 else ImportStatus.PARTIAL
    return status, detalhe


def failure_of(exc: Exception) -> tuple[ImportStatus, str, datetime]:
    mensagem = str(exc) if isinstance(exc, SigmaUnavailable) else f"Falha inesperada: {exc}"
    return ImportStatus.FAILED, mensagem, datetime.now()


def visitors_summary(report: SigmaVisitorReport) -> str:
    total = report.created + report.updated
    texto = f"Visitantes sem facial: {total} no pMoni"
    mudancas = []
    if report.created:
        mudancas.append(f"{report.created} novos")
    if report.removed:
        mudancas.append(f"{report.removed} removidos")
    return f"{texto} ({', '.join(mudancas)})." if mudancas else f"{texto}."
