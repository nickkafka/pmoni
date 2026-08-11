from datetime import datetime, time

from sqlalchemy.orm import Session

from app.application.ports.automation_repository import AutomationRepository
from app.domain.entities.automation import ImportAutomation, ImportStatus
from app.infrastructure.persistence.models import ImportAutomationRecord

ROW_ID = 1
"""One installation, one routine: the row is created by the migration."""

DEFAULT_RUN_AT = time(3, 0)


class SqlAlchemyAutomationRepository(AutomationRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> ImportAutomation:
        return self._to_entity(self._record())

    def save_schedule(self, *, enabled: bool, run_at: time) -> ImportAutomation:
        record = self._record()
        record.enabled = enabled
        record.run_at = run_at.strftime("%H:%M")
        self._session.commit()
        self._session.refresh(record)
        return self._to_entity(record)

    def record_run(
        self, *, finished_at: datetime, status: ImportStatus, message: str
    ) -> ImportAutomation:
        record = self._record()
        record.last_run_at = finished_at
        record.last_status = str(status)
        record.last_message = message[:1024]
        self._session.commit()
        self._session.refresh(record)
        return self._to_entity(record)

    def _record(self) -> ImportAutomationRecord:
        record = self._session.get(ImportAutomationRecord, ROW_ID)
        if record is None:
            # A database created by `Base.metadata.create_all`, as the tests do, has
            # the table but not the row the migration inserts.
            record = ImportAutomationRecord(id=ROW_ID, enabled=False, run_at="03:00")
            self._session.add(record)
            self._session.commit()
            self._session.refresh(record)
        return record

    @staticmethod
    def _to_entity(record: ImportAutomationRecord) -> ImportAutomation:
        return ImportAutomation(
            enabled=record.enabled,
            run_at=_parse_time(record.run_at),
            last_run_at=record.last_run_at,
            last_status=ImportStatus(record.last_status) if record.last_status else None,
            last_message=record.last_message,
        )


def _parse_time(value: str) -> time:
    """A stored time that cannot be read must not stop the application from starting.

    The column only ever receives a formatted time, so this is a guard against a
    hand-edited database rather than an expected path.
    """
    try:
        hour, minute = value.split(":")
        return time(int(hour), int(minute))
    except (ValueError, TypeError):
        return DEFAULT_RUN_AT
