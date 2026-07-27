from dataclasses import dataclass

from app.application.ports.device_repository import DeviceRepository
from app.domain.entities.device import Device


class CredentialCipher:
    def encrypt(self, plaintext: str) -> str:
        raise NotImplementedError


@dataclass(slots=True)
class DeviceService:
    repository: DeviceRepository
    credential_cipher: CredentialCipher

    def register(self, device: Device, password: str) -> Device:
        if not password:
            raise ValueError("A senha do dispositivo é obrigatória.")
        return self.repository.add(device, self.credential_cipher.encrypt(password))

    def list_enabled(self) -> list[Device]:
        return self.repository.list_enabled()
