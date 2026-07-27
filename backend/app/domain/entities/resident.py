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
    """Person known to Monikraft, joined to external systems by ``employee_no``."""

    id: int
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
