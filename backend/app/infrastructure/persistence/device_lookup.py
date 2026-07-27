from collections.abc import Callable

from sqlalchemy.orm import Session

from app.application.ports.device_lookup import DeviceLookup
from app.domain.entities.access_event import DeviceSummary
from app.infrastructure.persistence.device_repository import SqlAlchemyDeviceRepository


class SessionScopedDeviceLookup(DeviceLookup):
    """Opens a short-lived session per lookup, so a renamed device shows up at once."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def find(self, device_id: int) -> DeviceSummary | None:
        session = self._session_factory()
        try:
            device = SqlAlchemyDeviceRepository(session).get(device_id)
            return DeviceSummary(device_id, device.name) if device else None
        finally:
            session.close()
