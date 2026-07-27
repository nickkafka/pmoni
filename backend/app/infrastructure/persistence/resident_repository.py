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
        records = self._session.scalars(select(ResidentRecord).order_by(ResidentRecord.name))
        return [self._to_entity(record) for record in records]

    def get_by_employee_no(self, employee_no: str) -> Resident | None:
        record = self._find(employee_no)
        return self._to_entity(record) if record else None

    def get_photo(self, employee_no: str) -> bytes | None:
        record = self._find(employee_no)
        return record.photo if record else None

    def photo_reference_of(self, employee_no: str) -> str | None:
        record = self._find(employee_no)
        if record is None or record.photo is None:
            return None
        return record.photo_reference

    def save_enrollment(
        self, person: EnrolledPerson, *, photo: bytes | None, device_id: int | None
    ) -> bool:
        record = self._find(person.employee_no)
        created = record is None
        if record is None:
            record = ResidentRecord(employee_no=person.employee_no)
            self._session.add(record)
        record.name = person.name
        record.source_device_id = device_id
        record.synced_at = datetime.now(UTC)
        if photo is not None:
            record.photo = photo
            record.photo_reference = person.photo_reference
        self._session.commit()
        return created

    def set_location(self, employee_no: str, *, apartment: str | None, block: str | None) -> Resident | None:
        record = self._find(employee_no)
        if record is None:
            return None
        record.apartment, record.block = apartment, block
        self._session.commit()
        self._session.refresh(record)
        return self._to_entity(record)

    def _find(self, employee_no: str) -> ResidentRecord | None:
        return self._session.scalar(
            select(ResidentRecord).where(ResidentRecord.employee_no == employee_no)
        )

    @staticmethod
    def _to_entity(record: ResidentRecord) -> Resident:
        return Resident(
            id=record.id, employee_no=record.employee_no, name=record.name,
            apartment=record.apartment, block=record.block,
            has_photo=record.photo is not None, synced_at=record.synced_at,
        )
