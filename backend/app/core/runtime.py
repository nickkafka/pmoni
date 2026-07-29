from datetime import timedelta

from fastapi import FastAPI

from app.application.services.access_event_enricher import AccessEventEnricher
from app.application.services.admin_sessions import AdminSessions
from app.application.services.device_manager import DeviceManager
from app.core.config import Settings, settings
from app.core.logger import logger
from app.database.database import SessionLocal
from app.hikvision.factory import HikvisionClientFactory
from app.infrastructure.persistence.device_lookup import SessionScopedDeviceLookup
from app.infrastructure.persistence.device_repository import SqlAlchemyDeviceRepository
from app.infrastructure.persistence.resident_lookup import SessionScopedResidentLookup
from app.infrastructure.security import FernetCredentialCipher
from app.infrastructure.snapshot_store import InMemorySnapshotStore


class ApplicationRuntime:
    """Owns process-wide services and their orderly lifecycle."""

    def __init__(self) -> None:
        self._session = None
        self.device_manager: DeviceManager | None = None
        self.access_events: AccessEventEnricher | None = None
        self.snapshots: InMemorySnapshotStore | None = None

    async def start(self, app: FastAPI) -> None:
        app.state.admin_sessions = self._build_admin_sessions()
        if not settings.DEVICE_CREDENTIALS_KEY:
            logger.warning("Monitoramento de dispositivos desabilitado: DEVICE_CREDENTIALS_KEY não configurada.")
            app.state.device_manager = None
            app.state.access_events = None
            app.state.snapshots = None
            return
        self._session = SessionLocal()
        repository = SqlAlchemyDeviceRepository(self._session)
        cipher = FernetCredentialCipher(settings.DEVICE_CREDENTIALS_KEY)
        self.snapshots = InMemorySnapshotStore()
        self.device_manager = DeviceManager(
            repository, HikvisionClientFactory(repository, cipher, self.snapshots)
        )
        await self.device_manager.start()
        self.access_events = AccessEventEnricher(
            self.device_manager,
            SessionScopedResidentLookup(SessionLocal),
            SessionScopedDeviceLookup(SessionLocal),
        )
        await self.access_events.start()
        app.state.device_manager = self.device_manager
        app.state.access_events = self.access_events
        app.state.snapshots = self.snapshots

    @staticmethod
    def _build_admin_sessions() -> AdminSessions:
        if settings.ADMIN_PASSWORD == Settings.model_fields["ADMIN_PASSWORD"].default:
            logger.warning(
                "A administração está com a senha padrão. Defina ADMIN_PASSWORD antes "
                "de expor o Monikraft fora da rede local."
            )
        return AdminSessions(
            username=settings.ADMIN_USERNAME,
            password=settings.ADMIN_PASSWORD,
            lifetime=timedelta(minutes=settings.ADMIN_SESSION_MINUTES),
        )

    async def stop(self) -> None:
        if self.access_events is not None:
            await self.access_events.stop()
            self.access_events = None
        if self.device_manager is not None:
            await self.device_manager.stop()
            self.device_manager = None
        if self._session is not None:
            self._session.close()
            self._session = None
