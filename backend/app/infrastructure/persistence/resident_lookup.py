from collections.abc import Callable
from dataclasses import replace

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

    def find(self, device_id: int, employee_no: str) -> ResidentSummary | None:
        session = self._session_factory()
        try:
            repository = SqlAlchemyResidentRepository(session)
            resident = repository.find(device_id, employee_no)
            if resident is None:
                return None
            summary = resident.to_summary()
            if summary.photo_id is not None:
                return summary
            # Equipamentos que guardam o rosto só como template deixam o cadastro sem
            # imagem. A mesma pessoa costuma ter foto em outra facial, e o porteiro
            # precisa vê-la para conferir quem passou.
            borrowed = repository.find_photo_holder(resident.employee_no, resident.name)
            return summary if borrowed is None else replace(summary, photo_id=borrowed)
        finally:
            session.close()
