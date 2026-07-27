from abc import ABC, abstractmethod

from app.application.ports.device_client import DeviceClient
from app.domain.entities.device import Device


class DeviceClientFactory(ABC):
    """Builds the appropriate manufacturer client for a registered device."""

    @abstractmethod
    def create(self, device: Device) -> DeviceClient:
        raise NotImplementedError
