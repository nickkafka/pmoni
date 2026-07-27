from app.application.ports.device_client import DeviceClient
from app.application.ports.device_client_factory import DeviceClientFactory
from app.application.ports.device_credentials_store import DeviceCredentialsStore
from app.application.ports.person_directory import PersonDirectory
from app.application.ports.person_directory_factory import PersonDirectoryFactory
from app.domain.entities.device import Device
from app.hikvision.client import HikvisionClient
from app.hikvision.directory import HikvisionPersonDirectory
from app.hikvision.session import IsapiSession
from app.infrastructure.security import FernetCredentialCipher


class _HikvisionCredentials:
    """Decrypts a device password only while a Hikvision adapter is being built."""

    def __init__(self, credentials_store: DeviceCredentialsStore, cipher: FernetCredentialCipher) -> None:
        self._credentials_store = credentials_store
        self._cipher = cipher

    def resolve(self, device: Device) -> tuple[int, str]:
        """Return the persisted identifier and the decrypted password of the device."""
        if device.id is None:
            raise ValueError("O dispositivo precisa estar persistido para criar um cliente.")
        encrypted_credentials = self._credentials_store.get_encrypted_credentials(device.id)
        if not encrypted_credentials:
            raise ValueError(f"Dispositivo {device.id} não possui credenciais configuradas.")
        return device.id, self._cipher.decrypt(encrypted_credentials)


class HikvisionClientFactory(DeviceClientFactory):
    def __init__(self, credentials_store: DeviceCredentialsStore, cipher: FernetCredentialCipher) -> None:
        self._credentials = _HikvisionCredentials(credentials_store, cipher)

    def create(self, device: Device) -> DeviceClient:
        device_id, password = self._credentials.resolve(device)
        return HikvisionClient(
            device_id=device_id, host=device.host, port=device.port,
            username=device.username, password=password,
        )


class HikvisionPersonDirectoryFactory(PersonDirectoryFactory):
    def __init__(self, credentials_store: DeviceCredentialsStore, cipher: FernetCredentialCipher) -> None:
        self._credentials = _HikvisionCredentials(credentials_store, cipher)

    def create(self, device: Device) -> PersonDirectory:
        device_id, password = self._credentials.resolve(device)
        return HikvisionPersonDirectory(
            session=IsapiSession(
                base_url=f"http://{device.host}:{device.port}",
                username=device.username, password=password,
            ),
            device_id=device_id,
        )
