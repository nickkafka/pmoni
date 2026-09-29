"""
The nightly routine that keeps the directory current.

Someone is enrolled on the equipment during the day and, until now, only appeared in
pMoni when an operator remembered to press synchronise. The porter looking that
person up would not find them. Running once a day closes that gap without anyone
having to remember.

Two stages, in this order: the facials, then Sigma. Somebody enrolled during the day
only exists in pMoni once the equipment has been read, and Sigma is what turns that
name into an apartment, a CPF and an RG. Running Sigma first would find nobody to
attach any of it to, and that person would stay incomplete until the next night.

Between two nights, a lighter check asks each facial every few minutes how many
people and faces it holds. Whoever was enrolled after the nightly run passes the
gate with no name and no picture until the next one; a count that no longer matches
what pMoni stored is what gives that away, and only that facial is synced.
"""

import asyncio

from collections.abc import Callable
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from app.application.ports.person_directory_factory import PersonDirectoryFactory
from app.application.services.resident_sync import ResidentSyncService
from app.application.services.sigma_import import (
    SigmaImportService,
    outcome_of,
    visitors_summary,
)
from app.core.config import settings
from app.core.logger import logger
from app.domain.entities.automation import ImportAutomation, ImportStatus
from app.domain.entities.device import Device
from app.domain.entities.resident import EnrollmentCount
from app.infrastructure.persistence.automation_repository import SqlAlchemyAutomationRepository
from app.infrastructure.persistence.device_repository import SqlAlchemyDeviceRepository
from app.infrastructure.persistence.resident_repository import SqlAlchemyResidentRepository
from app.infrastructure.persistence.sigma_repository import SqlAlchemySigmaRepository
from app.infrastructure.security import FernetCredentialCipher
from app.sigma.client import SigmaClient, SigmaUnavailable

JOB_ID = "importacao-diaria"
CHECK_JOB_ID = "verificacao-faciais"

_SEVERITY = {ImportStatus.OK: 0, ImportStatus.PARTIAL: 1, ImportStatus.FAILED: 2}


def _worst_of(*status: ImportStatus) -> ImportStatus:
    """The routine is only as good as its worst half.

    Facials fine and Sigma broken still leaves people without an apartment, and a
    green light on the screen would say the night went well when it did not.
    """
    return max(status, key=lambda item: _SEVERITY[item])


class DailyImportScheduler:
    """Runs the import at the hour the operator chose, and remembers how it went."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        directory_factory: PersonDirectoryFactory,
    ) -> None:
        self._session_factory = session_factory
        self._directory_factory = directory_factory
        self._scheduler: AsyncIOScheduler | None = None
        # The nightly run and the check both sync devices, and two syncs of the same
        # facial at once would fight over the same rows.
        self._lock = asyncio.Lock()
        # What each facial reported the last time the check synced it. A device that
        # keeps an entry the sync skips — a user with no name, a face with no image —
        # never matches the local count, and without this it would be synced again
        # on every check. It is synced once more only when its own count moves.
        self._settled: dict[int, EnrollmentCount] = {}

    async def start(self) -> None:
        self._scheduler = AsyncIOScheduler()
        self._scheduler.start()
        self.apply(self._read_schedule())

    async def stop(self) -> None:
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None

    def apply(self, automation: ImportAutomation) -> None:
        """Point the routine at a new hour, or take it off the calendar."""
        if self._scheduler is None:
            return
        self._apply_check(automation)
        existing = self._scheduler.get_job(JOB_ID)
        if existing is not None:
            existing.remove()
        if not automation.enabled:
            logger.info("Importação automática desligada.")
            return
        self._scheduler.add_job(
            self.run,
            CronTrigger(hour=automation.run_at.hour, minute=automation.run_at.minute),
            id=JOB_ID,
            # An import that overruns must not have a second one started on top of
            # it: they would fight over the same devices and the same rows.
            max_instances=1,
            coalesce=True,
        )
        logger.info("Importação automática às {}.", automation.run_at.strftime("%H:%M"))

    async def run(self) -> ImportAutomation:
        """Import from every enabled device, and record the outcome either way.

        Nothing raises out of here. This is called by the scheduler, where an escaping
        exception only reaches a log nobody reads — and would leave the screen showing
        the previous run as though it were the last one.
        """
        async with self._lock:
            return await self._run()

    async def _run(self) -> ImportAutomation:
        session = self._session_factory()
        try:
            status, message = await self._import(session)
            sigma = await self._import_sigma(session)
            if sigma is not None:
                status, message = _worst_of(status, sigma[0]), f"{message} Sigma: {sigma[1]}"
        except Exception as exc:
            logger.exception("A importação automática falhou.")
            status, message = ImportStatus.FAILED, f"Falha inesperada: {exc}"
        try:
            return SqlAlchemyAutomationRepository(session).record_run(
                finished_at=datetime.now(), status=status, message=message
            )
        finally:
            session.close()

    async def _import_sigma(self, session: Session) -> tuple[ImportStatus, str] | None:
        """Fill in from Sigma what the facials just brought, or say why it was skipped.

        Runs after the equipment on purpose: somebody enrolled this morning only
        exists locally once the facials have been read, and asking Sigma about them
        before that would find nobody to attach the apartment to.

        A Sigma that is not configured is not a failure — most of the routine's value
        is the facial sync, and reporting an error every night for an integration the
        operator has not set up would train them to ignore the message.
        """
        sigma = SqlAlchemySigmaRepository(session)
        integration = sigma.get()
        if not integration.configured or integration.account_id is None:
            logger.info("Importação do Sigma pulada: integração não configurada.")
            return None

        try:
            cipher = FernetCredentialCipher(settings.DEVICE_CREDENTIALS_KEY)
            client = SigmaClient(cipher.decrypt(sigma.encrypted_token()))
        except Exception as exc:
            return ImportStatus.FAILED, f"não foi possível abrir a conexão ({exc})."

        try:
            report = await SigmaImportService(SqlAlchemyResidentRepository(session)).run(
                client, integration.account_id
            )
        except SigmaUnavailable as exc:
            sigma.record_import(
                finished_at=datetime.now(), status=ImportStatus.FAILED, message=str(exc)
            )
            return ImportStatus.FAILED, str(exc)
        except Exception as exc:
            logger.exception("A importação do Sigma falhou dentro da rotina diária.")
            mensagem = f"falha inesperada ({exc})."
            sigma.record_import(
                finished_at=datetime.now(), status=ImportStatus.FAILED, message=mensagem
            )
            return ImportStatus.FAILED, mensagem
        finally:
            await client.close()

        status, mensagem = outcome_of(report)
        # Gravado também no painel do Sigma: quem olha lá quer a data da última
        # importação, tenha ela vindo do botão ou da rotina.
        sigma.record_import(finished_at=datetime.now(), status=status, message=mensagem)
        return status, mensagem

    async def _import(self, session: Session) -> tuple[ImportStatus, str]:
        devices = SqlAlchemyDeviceRepository(session)
        service = ResidentSyncService(
            SqlAlchemyResidentRepository(session), self._directory_factory
        )

        enabled = devices.list_enabled()
        if not enabled:
            return ImportStatus.FAILED, "Nenhum equipamento habilitado para importar."

        created = updated = removed = 0
        failed: list[str] = []
        for device in enabled:
            try:
                report = await service.sync(device)
            except Exception as exc:
                logger.exception("Importação falhou no equipamento {}.", device.name)
                failed.append(f"{device.name} ({type(exc).__name__})")
                continue
            created += report.created
            updated += report.updated
            removed += report.removed

        summary = (
            f"{len(enabled) - len(failed)} de {len(enabled)} equipamentos: "
            f"{created} novos, {updated} atualizados, {removed} removidos."
        )
        if not failed:
            return ImportStatus.OK, summary
        # Everything failing is a different problem from one gate being unplugged,
        # and the operator looks for a different cause in each case.
        status = ImportStatus.FAILED if len(failed) == len(enabled) else ImportStatus.PARTIAL
        return status, f"{summary} Sem resposta: {', '.join(failed)}."

    def _apply_check(self, automation: ImportAutomation) -> None:
        existing = self._scheduler.get_job(CHECK_JOB_ID)
        if existing is not None:
            existing.remove()
        if not automation.check_enabled:
            logger.info("Verificação periódica das faciais desligada.")
            return
        self._scheduler.add_job(
            self.check,
            IntervalTrigger(minutes=automation.check_interval_minutes),
            id=CHECK_JOB_ID,
            max_instances=1,
            coalesce=True,
        )
        logger.info(
            "Verificação das faciais a cada {} minuto(s).", automation.check_interval_minutes
        )

    async def check(self) -> ImportAutomation:
        """Sync only the facials whose count disagrees with pMoni, then Sigma.

        Like ``run``, nothing raises out of here, and the outcome is recorded either
        way: a check that silently stopped working looks exactly like one that finds
        nothing to do.
        """
        async with self._lock:
            session = self._session_factory()
            try:
                message = await self._check(session)
            except Exception as exc:
                logger.exception("A verificação das faciais falhou.")
                message = f"Falha inesperada: {exc}"
            try:
                return SqlAlchemyAutomationRepository(session).record_check(
                    finished_at=datetime.now(), message=message
                )
            finally:
                session.close()

    async def _check(self, session: Session) -> str:
        devices = SqlAlchemyDeviceRepository(session)
        residents = SqlAlchemyResidentRepository(session)
        service = ResidentSyncService(residents, self._directory_factory)

        enabled = devices.list_enabled()
        if not enabled:
            return "Nenhum equipamento habilitado para verificar."

        synced: list[str] = []
        failed: list[str] = []
        created = 0
        for device in enabled:
            try:
                on_device = await self._count(device)
            except Exception as exc:
                logger.warning("Não foi possível contar os cadastros de {}: {}", device.name, exc)
                failed.append(device.name)
                continue
            stored = residents.enrollment_count(device.id)
            if on_device == stored or self._settled.get(device.id) == on_device:
                continue

            logger.info(
                "Facial {} tem {} pessoa(s) e {} rosto(s); o pMoni tem {} e {}. Sincronizando.",
                device.name, on_device.users, on_device.faces, stored.users, stored.faces,
            )
            try:
                report = await service.sync(device)
            except Exception:
                logger.exception("Sincronização falhou na verificação de {}.", device.name)
                failed.append(device.name)
                continue
            self._settled[device.id] = on_device
            created += report.created
            synced.append(
                f"{device.name} ({report.created} novos, {report.photos_downloaded} fotos, "
                f"{report.removed} removidos)"
            )

        if synced:
            message = f"Sincronizadas: {', '.join(synced)}."
        else:
            message = (
                f"{len(enabled) - len(failed)} de {len(enabled)} faciais conferidas, "
                "nada a sincronizar."
            )
        if failed:
            message += f" Sem resposta: {', '.join(failed)}."
        # A importação inteira do Sigma só quando alguém chegou às faciais: rodá-la a
        # cada verificação pediria centenas de fotos dezenas de vezes por dia. Os
        # visitantes, esses sim, são conferidos toda vez — são cadastrados no Sigma
        # ao longo do dia, e o porteiro precisa encontrá-los assim que chegam.
        if created:
            sigma = await self._import_sigma(session)
            if sigma is not None:
                message += f" Sigma: {sigma[1]}"
        else:
            visitors = await self._check_sigma_visitors(session)
            if visitors is not None:
                message += f" {visitors}"
        return message

    async def _check_sigma_visitors(self, session: Session) -> str | None:
        """Bring in the visitors registered in Sigma since the last check."""
        sigma = SqlAlchemySigmaRepository(session)
        integration = sigma.get()
        if not integration.configured or integration.account_id is None:
            return None
        try:
            cipher = FernetCredentialCipher(settings.DEVICE_CREDENTIALS_KEY)
            client = SigmaClient(cipher.decrypt(sigma.encrypted_token()))
        except Exception as exc:
            return f"Visitantes do Sigma: não foi possível abrir a conexão ({exc})."
        try:
            report = await SigmaImportService(SqlAlchemyResidentRepository(session)).run_visitors(
                client, integration.account_id
            )
        except SigmaUnavailable as exc:
            return f"Visitantes do Sigma: falha ({exc})."
        except Exception as exc:
            logger.exception("A verificação dos visitantes do Sigma falhou.")
            return f"Visitantes do Sigma: falha inesperada ({exc})."
        finally:
            await client.close()
        return visitors_summary(report)

    async def _count(self, device: Device) -> EnrollmentCount:
        directory = self._directory_factory.create(device)
        try:
            return await directory.count_enrolled()
        finally:
            await directory.close()

    def _read_schedule(self) -> ImportAutomation:
        session = self._session_factory()
        try:
            return SqlAlchemyAutomationRepository(session).get()
        finally:
            session.close()
