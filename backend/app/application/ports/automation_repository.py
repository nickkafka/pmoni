from abc import ABC, abstractmethod
from datetime import datetime, time

from app.domain.entities.automation import ImportAutomation, ImportStatus


class AutomationRepository(ABC):
    """Stores the daily import schedule and the outcome of its last run."""

    @abstractmethod
    def get(self) -> ImportAutomation:
        """Always answers: the row exists from the migration onwards."""
        raise NotImplementedError

    @abstractmethod
    def save_schedule(self, *, enabled: bool, run_at: time) -> ImportAutomation:
        """Change when the routine runs, leaving the last outcome untouched."""
        raise NotImplementedError

    @abstractmethod
    def record_run(
        self, *, finished_at: datetime, status: ImportStatus, message: str
    ) -> ImportAutomation:
        """Record how a run ended, leaving the schedule untouched."""
        raise NotImplementedError
