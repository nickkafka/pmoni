from abc import ABC, abstractmethod
from collections.abc import Mapping

from app.domain.entities.resident import EnrolledPerson, Resident


class ResidentRepository(ABC):
    """Stores enrollments, which are only unique per device."""

    @abstractmethod
    def list_all(self) -> list[Resident]:
        raise NotImplementedError

    @abstractmethod
    def list_directory(self) -> list[Resident]:
        """Every enrollment, cheap enough to read on demand.

        Same rows as ``list_all`` without the photo bytes, so a search can read the
        whole directory without moving the images with it.
        """
        raise NotImplementedError

    @abstractmethod
    def find(self, device_id: int, employee_no: str) -> Resident | None:
        raise NotImplementedError

    @abstractmethod
    def get_photo(self, resident_id: int) -> bytes | None:
        raise NotImplementedError

    @abstractmethod
    def find_photo_holder(self, employee_no: str, name: str) -> int | None:
        """Any enrollment of this person that has a picture, from whichever device.

        Matched by identifier *and* name: the identifier alone names different people
        on devices enrolled separately, and borrowing across that would show the
        wrong face.
        """
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
    def set_person_details(
        self, employee_no: str, name: str, changes: Mapping[str, str | None]
    ) -> list[Resident]:
        """Write what pMoni knows about a person onto every enrollment naming them.

        This is the door the Sigma import comes through: it learns apartment, block
        and document per person and has no notion of which equipment holds which
        enrollment.

        Only the fields in ``changes`` are touched, and ``None`` in it clears one.
        Returns the enrollments written.
        """
        raise NotImplementedError

    @abstractmethod
    def drop_missing(self, device_id: int, keep: set[str]) -> int:
        """Delete this device's enrollments whose identifiers it no longer reports."""
        raise NotImplementedError

    @abstractmethod
    def drop_all(self) -> int:
        """Empty the directory. Synchronising the devices again rebuilds it."""
        raise NotImplementedError
