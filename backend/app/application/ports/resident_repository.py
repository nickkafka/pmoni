from abc import ABC, abstractmethod

from app.domain.entities.resident import EnrolledPerson, Resident


class ResidentRepository(ABC):
    """Stores enrollments, which are only unique per device."""

    @abstractmethod
    def list_all(self) -> list[Resident]:
        raise NotImplementedError

    @abstractmethod
    def find(self, device_id: int, employee_no: str) -> Resident | None:
        raise NotImplementedError

    @abstractmethod
    def get_photo(self, resident_id: int) -> bytes | None:
        raise NotImplementedError

    @abstractmethod
    def photo_reference_of(self, device_id: int, employee_no: str) -> str | None:
        """Return the stored enrollment reference, used to skip unchanged photos."""
        raise NotImplementedError

    @abstractmethod
    def save_enrollment(self, device_id: int, person: EnrolledPerson, *, photo: bytes | None) -> bool:
        """Create or refresh the enrollment, keeping the locally managed location.

        Returns ``True`` when a new enrollment was created.
        """
        raise NotImplementedError

    @abstractmethod
    def set_location(self, resident_id: int, *, apartment: str | None, block: str | None) -> Resident | None:
        raise NotImplementedError

    @abstractmethod
    def drop_missing(self, device_id: int, keep: set[str]) -> int:
        """Delete this device's enrollments whose identifiers it no longer reports."""
        raise NotImplementedError

    @abstractmethod
    def drop_all(self) -> int:
        """Empty the directory. Synchronising the devices again rebuilds it."""
        raise NotImplementedError
