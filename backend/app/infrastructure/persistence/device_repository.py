from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.ports.device_repository import DeviceRepository
from app.application.ports.device_credentials_store import DeviceCredentialsStore
from app.domain.entities.device import Device
from app.infrastructure.persistence.models import DeviceRecord


class SqlAlchemyDeviceRepository(DeviceRepository, DeviceCredentialsStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, device: Device, encrypted_credentials: str) -> Device:
        record = DeviceRecord(
            name=device.name, host=device.host, port=device.port, username=device.username,
            credentials_encrypted=encrypted_credentials, model=device.model, enabled=device.enabled,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return self._to_entity(record)

    def get(self, device_id: int) -> Device | None:
        record = self._session.get(DeviceRecord, device_id)
        return self._to_entity(record) if record else None

    def list_enabled(self) -> list[Device]:
        records = self._session.scalars(select(DeviceRecord).where(DeviceRecord.enabled.is_(True)).order_by(DeviceRecord.name))
        return [self._to_entity(record) for record in records]

    def get_encrypted_credentials(self, device_id: int) -> str | None:
        record = self._session.get(DeviceRecord, device_id)
        return record.credentials_encrypted if record else None

    @staticmethod
    def _to_entity(record: DeviceRecord) -> Device:
        return Device(record.id, record.name, record.host, record.port, record.username, record.model, record.enabled)
