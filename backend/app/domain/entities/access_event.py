from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.resident import ResidentSummary


@dataclass(slots=True)
class AccessEvent:
    """Normalized event emitted by any access-control manufacturer."""

    external_id: str
    device_id: int
    employee_no: str | None
    access_type: str
    success: bool
    event_time: datetime
    snapshot: str | None = None


@dataclass(frozen=True, slots=True)
class EnrichedAccessEvent:
    """Presentation-ready event, never used as a device integration input."""

    event: AccessEvent
    resident: ResidentSummary | None
