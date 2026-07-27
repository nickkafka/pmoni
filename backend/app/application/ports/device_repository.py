from abc import ABC, abstractmethod

from app.domain.entities.device import Device


class DeviceRepository(ABC):
    @abstractmethod
    def add(self, device: Device, encrypted_credentials: str) -> Device:
        raise NotImplementedError

    @abstractmethod
    def get(self, device_id: int) -> Device | None:
        raise NotImplementedError

    @abstractmethod
    def list_enabled(self) -> list[Device]:
        raise NotImplementedError
