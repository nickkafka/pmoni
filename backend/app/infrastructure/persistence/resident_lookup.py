from collections.abc import Callable

from sqlalchemy.orm import Session

from app.application.ports.resident_lookup import ResidentLookup
from app.domain.entities.resident import ResidentSummary
from app.infrastructure.persistence.resident_repository import SqlAlchemyResidentRepository


class SessionScopedResidentLookup(ResidentLookup):
    """Opens a short-lived session per lookup.

    A session kept open for the whole process would keep serving the rows it had
    already loaded, so an apartment edited through the API would never reach the
    interface until the application restarted.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def find(self, employee_no: str) -> ResidentSummary | None:
        session = self._session_factory()
        try:
            resident = SqlAlchemyResidentRepository(session).get_by_employee_no(employee_no)
            return resident.to_summary() if resident else None
        finally:
            session.close()
