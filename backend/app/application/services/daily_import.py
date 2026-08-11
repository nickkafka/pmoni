"""
The nightly routine that keeps the directory current.

Someone is enrolled on the equipment during the day and, until now, only appeared in
pMoni when an operator remembered to press synchronise. The porter looking that
person up would not find them. Running once a day closes that gap without anyone
having to remember.

The Sigma import will join this same routine once its permissions are released: it
runs after the facials on purpose, because it fills in apartment and document for
people the facials have just brought in.
"""

from collections.abc import Callable
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.application.ports.person_directory_factory import PersonDirectoryFactory
from app.application.services.resident_sync import ResidentSyncService
from app.core.logger import logger
from app.domain.entities.automation import ImportAutomation, ImportStatus
from app.infrastructure.persistence.automation_repository import SqlAlchemyAutomationRepository
from app.infrastructure.persistence.device_repository import SqlAlchemyDeviceRepository
from app.infrastructure.persistence.resident_repository import SqlAlchemyResidentRepository

JOB_ID = "importacao-diaria"


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
        session = self._session_factory()
        try:
            status, message = await self._import(session)
        except Exception as exc:
            logger.exception("A importação automática falhou.")
            status, message = ImportStatus.FAILED, f"Falha inesperada: {exc}"
        try:
            return SqlAlchemyAutomationRepository(session).record_run(
                finished_at=datetime.now(), status=status, message=message
            )
        finally:
            session.close()

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

    def _read_schedule(self) -> ImportAutomation:
        session = self._session_factory()
        try:
            return SqlAlchemyAutomationRepository(session).get()
        finally:
            session.close()
