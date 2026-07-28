from abc import ABC, abstractmethod

from app.domain.entities.resident import ResidentSummary


class ResidentLookup(ABC):
    """Resolves the identifier carried by a device event into local resident data.

    The device is part of the question: identifiers are issued per device, so the
    same number names different people on devices enrolled separately.
    """

    @abstractmethod
    def find(self, device_id: int, employee_no: str) -> ResidentSummary | None:
        raise NotImplementedError
