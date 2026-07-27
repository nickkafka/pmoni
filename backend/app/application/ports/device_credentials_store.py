from abc import ABC, abstractmethod


class DeviceCredentialsStore(ABC):
    """Provides encrypted device credentials only to infrastructure factories."""

    @abstractmethod
    def get_encrypted_credentials(self, device_id: int) -> str | None:
        raise NotImplementedError
