from dataclasses import dataclass
from datetime import datetime, time
from enum import StrEnum


class ImportStatus(StrEnum):
    """How the last run ended, in the terms the operator has to act on.

    ``PARTIAL`` is the one worth separating: the import finished and the directory
    is usable, but at least one gate did not answer, so somebody enrolled only there
    is missing. Reporting that as success hides a real gap, and as failure would send
    the operator looking for a problem that mostly is not there.
    """

    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ImportAutomation:
    """The daily routine: when it runs, and how it went the last time."""

    enabled: bool
    run_at: time
    last_run_at: datetime | None = None
    last_status: ImportStatus | None = None
    last_message: str | None = None
