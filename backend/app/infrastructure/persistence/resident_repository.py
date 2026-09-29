from collections.abc import Mapping
from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.application.ports.resident_repository import ResidentRepository
from app.domain.entities.resident import EnrolledPerson, EnrollmentCount, Resident
from app.domain.entities.sigma import SIGMA_PHOTO_PREFIX, SigmaDweller
from app.infrastructure.persistence.models import ResidentRecord


PERSON_FIELDS = frozenset({"apartment", "block", "cpf", "rg"})
"""O que pertence à pessoa, e não ao equipamento que emitiu o cadastro."""


class SqlAlchemyResidentRepository(ResidentRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[Resident]:
        records = self._session.scalars(
            select(ResidentRecord).order_by(ResidentRecord.name, ResidentRecord.device_id)
        )
        return [self._to_entity(record) for record in records]

    def list_directory(self) -> list[Resident]:
        """Every enrollment, without the photo bytes.

        ``list_all`` loads whole rows, and each row carries a picture of about a
        hundred kilobytes. Reading the directory to answer a search would move tens
        of megabytes per keystroke, so the columns the search reads are selected
        explicitly and the image is left in the database.
        """
        rows = self._session.execute(
            select(
                ResidentRecord.id,
                ResidentRecord.device_id,
                ResidentRecord.employee_no,
                ResidentRecord.name,
                ResidentRecord.apartment,
                ResidentRecord.block,
                ResidentRecord.cpf,
                ResidentRecord.rg,
                ResidentRecord.active,
                ResidentRecord.photo.is_not(None).label("has_photo"),
                ResidentRecord.synced_at,
            ).order_by(ResidentRecord.name, ResidentRecord.id)
        ).all()
        return [
            Resident(
                id=row.id, device_id=row.device_id, employee_no=row.employee_no,
                name=row.name, apartment=row.apartment, block=row.block,
                has_photo=row.has_photo, synced_at=row.synced_at,
                cpf=row.cpf, rg=row.rg, active=row.active,
            )
            for row in rows
        ]

    def find(self, device_id: int, employee_no: str) -> Resident | None:
        record = self._find(device_id, employee_no)
        return self._to_entity(record) if record else None

    def get_photo(self, resident_id: int) -> bytes | None:
        record = self._session.get(ResidentRecord, resident_id)
        return record.photo if record else None

    def find_photo_holder(self, employee_no: str, name: str) -> int | None:
        return self._session.scalar(
            select(ResidentRecord.id)
            .where(
                ResidentRecord.employee_no == employee_no,
                ResidentRecord.name == name,
                ResidentRecord.photo.is_not(None),
            )
            # Estável entre chamadas, para a tela não trocar de foto sem motivo.
            .order_by(ResidentRecord.id)
            .limit(1)
        )

    def photo_reference_of(self, device_id: int, employee_no: str) -> str | None:
        record = self._find(device_id, employee_no)
        if record is None or record.photo is None:
            return None
        return record.photo_reference

    def enrollment_count(self, device_id: int) -> EnrollmentCount:
        # A referência só é gravada junto com a imagem, então contá-la conta quem tem
        # foto sem ler os bytes de cada uma. A foto do Sigma fica de fora: a facial
        # não a tem, e contá-la faria a verificação ver diferença onde não há.
        from_device = case(
            (ResidentRecord.photo_reference.startswith(SIGMA_PHOTO_PREFIX), None),
            else_=ResidentRecord.photo_reference,
        )
        users, faces = self._session.execute(
            select(func.count(), func.count(from_device)).where(
                ResidentRecord.device_id == device_id
            )
        ).one()
        return EnrollmentCount(users=users, faces=faces)

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

    def set_person_details(
        self, employee_no: str, name: str, changes: Mapping[str, str | None]
    ) -> list[Resident]:
        """Record what pMoni knows about a person on every enrollment that names them.

        Apartment, block and document belong to the person, not to any one piece of
        equipment, so writing them to a single enrollment would leave the same person
        answering differently depending on which gate they walked through.

        Identifier *and* name have to match, the rule ADR 0010 settled on: writing by
        identifier alone would spill one person's address onto another's enrollment on
        a device that reused the number.

        ``changes`` carries only the fields the caller means to write, and a ``None``
        in it clears that field. Absent and empty have to stay different things: an
        import that knows the apartment but not the document must not erase a document
        typed by hand, while an operator clearing the apartment box must not be told
        their change did nothing.
        """
        unknown = set(changes) - PERSON_FIELDS
        if unknown:
            raise ValueError(f"Campos desconhecidos: {', '.join(sorted(unknown))}.")
        if not changes:
            return []

        records = self._session.scalars(
            select(ResidentRecord).where(
                ResidentRecord.employee_no == employee_no,
                ResidentRecord.name == name,
            )
        ).all()
        for record in records:
            for field, value in changes.items():
                setattr(record, field, value)
        self._session.commit()
        return [self._to_entity(record) for record in records]

    def set_active(self, statuses: Mapping[tuple[str, str], bool]) -> int:
        if not statuses:
            return 0
        changed = 0
        records = self._session.scalars(
            select(ResidentRecord).where(
                ResidentRecord.employee_no.in_({employee_no for employee_no, _ in statuses})
            )
        ).all()
        for record in records:
            active = statuses.get((record.employee_no, record.name))
            if active is not None and record.active is not active:
                record.active = active
                changed += 1
        self._session.commit()
        return changed

    def sigma_visitors(self) -> dict[int, bool]:
        rows = self._session.execute(
            select(ResidentRecord.sigma_id, ResidentRecord.photo.is_not(None)).where(
                ResidentRecord.device_id.is_(None), ResidentRecord.sigma_id.is_not(None)
            )
        ).all()
        return {sigma_id: has_photo for sigma_id, has_photo in rows}

    def save_sigma_visitor(self, visitor: SigmaDweller, *, photo: bytes | None) -> bool:
        record = self._session.scalar(
            select(ResidentRecord).where(
                ResidentRecord.device_id.is_(None), ResidentRecord.sigma_id == visitor.sigma_id
            )
        )
        created = record is None
        if record is None:
            record = ResidentRecord(device_id=None, sigma_id=visitor.sigma_id)
            self._session.add(record)
        # Sem matrícula o visitante ainda precisa de um identificador, e o do Sigma é
        # o único que ele tem. Prefixado para nunca se confundir com o de uma facial.
        record.employee_no = visitor.enrollment or f"sigma-{visitor.sigma_id}"
        record.name = visitor.name
        record.apartment, record.block = visitor.apartment, visitor.block
        record.cpf, record.rg = visitor.cpf, visitor.rg
        record.active = visitor.enabled
        record.synced_at = datetime.now(UTC)
        if photo is not None:
            record.photo = photo
            record.photo_reference = f"{SIGMA_PHOTO_PREFIX}{visitor.sigma_id}"
        self._session.commit()
        return created

    def drop_sigma_visitors(self, keep: set[int]) -> int:
        stale = self._session.scalars(
            select(ResidentRecord).where(
                ResidentRecord.device_id.is_(None),
                ResidentRecord.sigma_id.not_in(keep) | ResidentRecord.sigma_id.is_(None),
            )
        ).all()
        for record in stale:
            self._session.delete(record)
        self._session.commit()
        return len(stale)

    def set_fallback_photo(
        self, employee_no: str, name: str, photo: bytes, *, reference: str
    ) -> int:
        records = self._session.scalars(
            select(ResidentRecord).where(
                ResidentRecord.employee_no == employee_no,
                ResidentRecord.name == name,
                ResidentRecord.photo.is_(None),
            )
        ).all()
        for record in records:
            record.photo = photo
            record.photo_reference = reference
        self._session.commit()
        return len(records)

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

    def drop_all(self) -> int:
        removed = self._session.query(ResidentRecord).delete()
        self._session.commit()
        return removed

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
            cpf=record.cpf, rg=record.rg, active=record.active,
        )
