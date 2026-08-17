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
from app.domain.entities.sigma import SigmaDweller, SigmaImportReport
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
        pessoas = await client.dwellers(account_id)
        logger.info("Sigma devolveu {} pessoa(s) na conta {}.", len(pessoas), account_id)

        # Lido uma vez: são centenas de cadastros, e consultar por pessoa faria uma
        # varredura do diretório inteiro para cada uma delas.
        por_identificador: dict[str, set[str]] = defaultdict(set)
        for enrollment in self._residents.list_directory():
            por_identificador[enrollment.employee_no].add(enrollment.name)

        updated = 0
        unmatched: list[str] = []
        for pessoa in pessoas:
            changes = _changes_of(pessoa)
            if not changes:
                # Está no Sigma sem nada que nos sirva: gravar isto seria escrever
                # nada e ainda contar como atualização.
                continue

            local = match_name(pessoa.name, por_identificador.get(pessoa.enrollment, set()))
            if local is None:
                unmatched.append(f"{pessoa.name} (ID {pessoa.enrollment})")
                continue
            # Gravado sob o nome que está no cadastro, não sob o do Sigma: é por ele
            # que as linhas daquela pessoa são encontradas.
            if self._residents.set_person_details(pessoa.enrollment, local, changes):
                updated += 1

        return SigmaImportReport(read=len(pessoas), updated=updated, unmatched=unmatched)


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
