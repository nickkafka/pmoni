from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.domain.entities.access_event import AccessEvent


class DeviceClient(ABC):
    """Manufacturer-neutral connection to one registered device."""

    @property
    @abstractmethod
    def device_id(self) -> int:
        raise NotImplementedError

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def events(self) -> AsyncIterator[AccessEvent]:
        """Yield normalized events until the connection closes."""
        raise NotImplementedError
