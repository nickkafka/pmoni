from fastapi import FastAPI

from app.application.services.access_event_enricher import AccessEventEnricher
from app.application.services.device_manager import DeviceManager
from app.core.config import settings
from app.core.logger import logger
from app.database.database import SessionLocal
from app.hikvision.factory import HikvisionClientFactory
from app.infrastructure.persistence.device_lookup import SessionScopedDeviceLookup
from app.infrastructure.persistence.device_repository import SqlAlchemyDeviceRepository
from app.infrastructure.persistence.resident_lookup import SessionScopedResidentLookup
from app.infrastructure.security import FernetCredentialCipher


class ApplicationRuntime:
    """Owns process-wide services and their orderly lifecycle."""

    def __init__(self) -> None:
        self._session = None
        self.device_manager: DeviceManager | None = None
        self.access_events: AccessEventEnricher | None = None

    async def start(self, app: FastAPI) -> None:
        if not settings.DEVICE_CREDENTIALS_KEY:
            logger.warning("Monitoramento de dispositivos desabilitado: DEVICE_CREDENTIALS_KEY não configurada.")
            app.state.device_manager = None
            app.state.access_events = None
            return
        self._session = SessionLocal()
        repository = SqlAlchemyDeviceRepository(self._session)
        cipher = FernetCredentialCipher(settings.DEVICE_CREDENTIALS_KEY)
        self.device_manager = DeviceManager(repository, HikvisionClientFactory(repository, cipher))
        await self.device_manager.start()
        self.access_events = AccessEventEnricher(
            self.device_manager,
            SessionScopedResidentLookup(SessionLocal),
            SessionScopedDeviceLookup(SessionLocal),
        )
        await self.access_events.start()
        app.state.device_manager = self.device_manager
        app.state.access_events = self.access_events

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
