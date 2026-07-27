from abc import ABC, abstractmethod

from app.domain.entities.resident import ResidentSummary


class ResidentLookup(ABC):
    """Resolves the identifier carried by a device event into local resident data."""

    @abstractmethod
    def find(self, employee_no: str) -> ResidentSummary | None:
        raise NotImplementedError
