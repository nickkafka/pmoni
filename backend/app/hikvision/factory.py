from app.application.ports.device_client import DeviceClient
from app.application.ports.device_client_factory import DeviceClientFactory
from app.application.ports.device_credentials_store import DeviceCredentialsStore
from app.domain.entities.device import Device
from app.hikvision.client import HikvisionClient
from app.infrastructure.security import FernetCredentialCipher


class HikvisionClientFactory(DeviceClientFactory):
    def __init__(self, credentials_store: DeviceCredentialsStore, cipher: FernetCredentialCipher) -> None:
        self._credentials_store = credentials_store
        self._cipher = cipher

    def create(self, device: Device) -> DeviceClient:
        if device.id is None:
            raise ValueError("O dispositivo precisa estar persistido para criar um cliente.")
        encrypted_credentials = self._credentials_store.get_encrypted_credentials(device.id)
        if not encrypted_credentials:
            raise ValueError(f"Dispositivo {device.id} não possui credenciais configuradas.")
        return HikvisionClient(
            device_id=device.id, host=device.host, port=device.port,
            username=device.username, password=self._cipher.decrypt(encrypted_credentials),
        )
