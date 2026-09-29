from datetime import datetime, time

from pydantic import BaseModel, Field

from app.domain.entities.automation import ImportAutomation, ImportStatus

CHECK_INTERVAL_LIMITS = {"ge": 1, "le": 1440}
"""De um minuto a um dia: acima disso a importação diária já cobre o intervalo."""


class ImportAutomationRead(BaseModel):
    enabled: bool
    run_at: str
    last_run_at: datetime | None
    last_status: ImportStatus | None
    last_message: str | None
    check_enabled: bool
    check_interval_minutes: int
    last_check_at: datetime | None
    last_check_message: str | None

    @classmethod
    def of(cls, automation: ImportAutomation) -> "ImportAutomationRead":
        return cls(
            enabled=automation.enabled,
            # "HH:MM" is what an <input type="time"> both sends and expects back.
            run_at=automation.run_at.strftime("%H:%M"),
            last_run_at=automation.last_run_at,
            last_status=automation.last_status,
            last_message=automation.last_message,
            check_enabled=automation.check_enabled,
            check_interval_minutes=automation.check_interval_minutes,
            last_check_at=automation.last_check_at,
            last_check_message=automation.last_check_message,
        )


class ImportAutomationUpdate(BaseModel):
    enabled: bool
    run_at: time = Field(
        description='Hora local da portaria, no formato "HH:MM".',
    )
    # Opcionais para que quem só mexe no horário não desligue a verificação sem
    # querer: ausentes, mantêm o que está gravado.
    check_enabled: bool | None = None
    check_interval_minutes: int | None = Field(
        default=None,
        description="De quantos em quantos minutos as faciais são conferidas.",
        **CHECK_INTERVAL_LIMITS,
    )
