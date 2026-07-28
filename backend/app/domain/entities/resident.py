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
    has_photo: bool = False


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
    device_id: int
    employee_no: str
    name: str
    apartment: str | None
    block: str | None
    has_photo: bool
    synced_at: datetime | None

    def to_summary(self) -> ResidentSummary:
        return ResidentSummary(
            self.id, self.employee_no, self.name, self.apartment, self.block, self.has_photo
        )
