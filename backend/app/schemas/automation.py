from datetime import datetime, time

from pydantic import BaseModel, Field

from app.domain.entities.automation import ImportAutomation, ImportStatus


class ImportAutomationRead(BaseModel):
    enabled: bool
    run_at: str
    last_run_at: datetime | None
    last_status: ImportStatus | None
    last_message: str | None

    @classmethod
    def of(cls, automation: ImportAutomation) -> "ImportAutomationRead":
        return cls(
            enabled=automation.enabled,
            # "HH:MM" is what an <input type="time"> both sends and expects back.
            run_at=automation.run_at.strftime("%H:%M"),
            last_run_at=automation.last_run_at,
            last_status=automation.last_status,
            last_message=automation.last_message,
        )


class ImportAutomationUpdate(BaseModel):
    enabled: bool
    run_at: time = Field(
        description='Hora local da portaria, no formato "HH:MM".',
    )
