from datetime import datetime
from typing import Any

from app.domain.entities.access_event import AccessEvent
from app.hikvision.exceptions import HikvisionEventParseError
from app.hikvision.urls import isapi_path

ACCESS_GRANTED_MINOR_CODES = frozenset({75})
"""Journal codes observed to identify a person and report the credential as accepted.

Every other code sampled across the device journal reports door hardware or a
rejection without identifying anyone, so it never reaches the domain.
"""


class AcsEventParser:
    """Converts access-control journal entries into Monikraft domain events."""

    def parse(self, entry: dict[str, Any], device_id: int) -> AccessEvent | None:
        """Return the normalized event, or ``None`` when no person was identified."""
        employee_no = entry.get("employeeNoString") or entry.get("employeeNo")
        if employee_no in (None, ""):
            return None
        serial_no = entry.get("serialNo")
        if serial_no is None:
            raise HikvisionEventParseError("Evento do journal sem número de série.")
        return AccessEvent(
            external_id=str(serial_no),
            device_id=device_id,
            employee_no=str(employee_no),
            access_type=str(entry.get("currentVerifyMode") or "unknown"),
            success=entry.get("minor") in ACCESS_GRANTED_MINOR_CODES,
            event_time=self._event_time(entry),
            snapshot=self._snapshot_path(entry),
        )

    @staticmethod
    def _snapshot_path(entry: dict[str, Any]) -> str | None:
        """Keep the device path; the published URL only survives on the device itself."""
        picture = entry.get("pictureURL")
        return isapi_path(str(picture)) if picture else None

    @staticmethod
    def _event_time(entry: dict[str, Any]) -> datetime:
        value = entry.get("time")
        if not value:
            raise HikvisionEventParseError("Evento do journal sem data e hora.")
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise HikvisionEventParseError("Data e hora do journal inválida.") from exc
