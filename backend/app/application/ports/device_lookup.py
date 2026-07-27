from abc import ABC, abstractmethod

from app.domain.entities.access_event import DeviceSummary


class DeviceLookup(ABC):
    """Resolves the device an event came from into what the porter should read."""

    @abstractmethod
    def find(self, device_id: int) -> DeviceSummary | None:
        raise NotImplementedError
