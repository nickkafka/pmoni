from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResidentSummary:
    """Resident data used only after an event has been locally enriched."""

    id: int
    employee_no: str
    name: str
    apartment: str | None
    block: str | None
