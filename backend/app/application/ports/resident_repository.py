from abc import ABC, abstractmethod

from app.domain.entities.resident import EnrolledPerson, Resident


class ResidentRepository(ABC):
    @abstractmethod
    def list_all(self) -> list[Resident]:
        raise NotImplementedError

    @abstractmethod
    def get_by_employee_no(self, employee_no: str) -> Resident | None:
        raise NotImplementedError

    @abstractmethod
    def get_photo(self, employee_no: str) -> bytes | None:
        raise NotImplementedError

    @abstractmethod
    def photo_reference_of(self, employee_no: str) -> str | None:
        """Return the stored enrollment reference, used to skip unchanged photos."""
        raise NotImplementedError

    @abstractmethod
    def save_enrollment(
        self, person: EnrolledPerson, *, photo: bytes | None, device_id: int | None
    ) -> bool:
        """Create or refresh the resident, keeping the locally managed location.

        Returns ``True`` when a new resident was created.
        """
        raise NotImplementedError

    @abstractmethod
    def set_location(self, employee_no: str, *, apartment: str | None, block: str | None) -> Resident | None:
        raise NotImplementedError
