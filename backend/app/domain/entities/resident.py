from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ResidentSummary:
    """Resident data used only after an event has been locally enriched."""

    id: int
    employee_no: str
    name: str
    apartment: str | None
    block: str | None
    photo_id: int | None = None
    """Enrollment holding the picture, which may be another device's.

    Some equipment stores a face only as a biometric template, so the enrollment the
    event came from often has no image while another one for the same person does.
    """
    active: bool | None = None
    """Whether Sigma has the person enabled; ``None`` when Sigma does not know them."""


@dataclass(frozen=True, slots=True)
class EnrolledPerson:
    """Person registered on a device, as delivered by any manufacturer.

    Devices only publish the identifier, the name and the enrollment photo, so the
    apartment is never part of this contract.
    """

    employee_no: str
    name: str
    photo_reference: str | None


@dataclass(frozen=True, slots=True)
class Resident:
    """One enrollment, as the device that issued ``employee_no`` knows it.

    The identifier is unique only within its device, so it never identifies a person
    on its own.
    """

    id: int
    device_id: int | None
    """``None`` for a visitor known only from Sigma, enrolled on no facial."""
    employee_no: str
    name: str
    apartment: str | None
    block: str | None
    has_photo: bool
    synced_at: datetime | None
    cpf: str | None = None
    rg: str | None = None
    active: bool | None = None
    """Whether Sigma has the person enabled; ``None`` when Sigma does not know them."""

    def to_summary(self) -> ResidentSummary:
        return ResidentSummary(
            self.id, self.employee_no, self.name, self.apartment, self.block,
            self.id if self.has_photo else None, self.active,
        )


@dataclass(frozen=True, slots=True)
class DirectoryPerson:
    """A person as the porter looks them up, gathered from every enrollment.

    Someone enrolled on five devices occupies five rows, and the porter searching for
    them wants one answer. Enrollments only count as the same person when identifier
    *and* name match — matching on the identifier alone is what ADR 0010 corrects,
    since separately enrolled devices reuse numbers for different people.

    What pMoni keeps about a person — apartment, block, CPF, RG — may have been
    recorded against any one of those enrollments, so the first value found for each
    field wins rather than the values of a single row.
    """

    employee_no: str
    name: str
    apartment: str | None
    block: str | None
    cpf: str | None
    rg: str | None
    photo_id: int | None
    device_ids: tuple[int, ...]
    active: bool | None = None
    """Whether Sigma has the person enabled; ``None`` when Sigma does not know them."""


@dataclass(frozen=True, slots=True)
class EnrollmentCount:
    """How many people a device holds, and how many of them have a face.

    Both numbers, because they go stale separately: someone enrolled after the last
    sync raises ``users``, while a face added later to somebody already there only
    raises ``faces`` — and that person shows up on the screen without a picture.
    """

    users: int
    faces: int
