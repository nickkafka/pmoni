from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.ports.resident_repository import ResidentRepository
from app.domain.entities.resident import EnrolledPerson, Resident
from app.infrastructure.persistence.models import ResidentRecord


class SqlAlchemyResidentRepository(ResidentRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[Resident]:
        records = self._session.scalars(
            select(ResidentRecord).order_by(ResidentRecord.name, ResidentRecord.device_id)
        )
        return [self._to_entity(record) for record in records]

    def find(self, device_id: int, employee_no: str) -> Resident | None:
        record = self._find(device_id, employee_no)
        return self._to_entity(record) if record else None

    def get_photo(self, resident_id: int) -> bytes | None:
        record = self._session.get(ResidentRecord, resident_id)
        return record.photo if record else None

    def photo_reference_of(self, device_id: int, employee_no: str) -> str | None:
        record = self._find(device_id, employee_no)
        if record is None or record.photo is None:
            return None
        return record.photo_reference

    def save_enrollment(self, device_id: int, person: EnrolledPerson, *, photo: bytes | None) -> bool:
        record = self._find(device_id, person.employee_no)
        created = record is None
        if record is None:
            record = ResidentRecord(device_id=device_id, employee_no=person.employee_no)
            self._session.add(record)
        record.name = person.name
        record.synced_at = datetime.now(UTC)
        if photo is not None:
            record.photo = photo
            record.photo_reference = person.photo_reference
        self._session.commit()
        return created

    def set_location(self, resident_id: int, *, apartment: str | None, block: str | None) -> Resident | None:
        record = self._session.get(ResidentRecord, resident_id)
        if record is None:
            return None
        record.apartment, record.block = apartment, block
        self._session.commit()
        self._session.refresh(record)
        return self._to_entity(record)

    def drop_missing(self, device_id: int, keep: set[str]) -> int:
        stale = self._session.scalars(
            select(ResidentRecord).where(
                ResidentRecord.device_id == device_id,
                ResidentRecord.employee_no.not_in(keep),
            )
        ).all()
        for record in stale:
            self._session.delete(record)
        self._session.commit()
        return len(stale)

    def _find(self, device_id: int, employee_no: str) -> ResidentRecord | None:
        return self._session.scalar(
            select(ResidentRecord).where(
                ResidentRecord.device_id == device_id,
                ResidentRecord.employee_no == employee_no,
            )
        )

    @staticmethod
    def _to_entity(record: ResidentRecord) -> Resident:
        return Resident(
            id=record.id, device_id=record.device_id, employee_no=record.employee_no,
            name=record.name, apartment=record.apartment, block=record.block,
            has_photo=record.photo is not None, synced_at=record.synced_at,
        )
