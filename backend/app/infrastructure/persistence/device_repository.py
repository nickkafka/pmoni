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

    def list_all(self) -> list[Device]:
        """Every device, disabled ones included.

        The import matches against this rather than against the enabled list: a
        device that was turned off is still registered, and matching only the enabled
        ones would quietly create a second row for the same equipment.
        """
        records = self._session.scalars(select(DeviceRecord).order_by(DeviceRecord.name))
        return [self._to_entity(record) for record in records]

    def update(self, device: Device, encrypted_credentials: str | None) -> Device | None:
        if device.id is None:
            return None
        record = self._session.get(DeviceRecord, device.id)
        if record is None:
            return None
        record.name, record.host, record.port = device.name, device.host, device.port
        record.username, record.model, record.enabled = device.username, device.model, device.enabled
        if encrypted_credentials is not None:
            record.credentials_encrypted = encrypted_credentials
        self._session.commit()
        self._session.refresh(record)
        return self._to_entity(record)

    def remove(self, device_id: int) -> bool:
        record = self._session.get(DeviceRecord, device_id)
        if record is None:
            return False
        self._session.delete(record)
        self._session.commit()
        return True

    def get_encrypted_credentials(self, device_id: int) -> str | None:
        record = self._session.get(DeviceRecord, device_id)
        return record.credentials_encrypted if record else None

    @staticmethod
    def _to_entity(record: DeviceRecord) -> Device:
        return Device(record.id, record.name, record.host, record.port, record.username, record.model, record.enabled)
