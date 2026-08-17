from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.entities.automation import ImportStatus
from app.domain.entities.sigma import SigmaIntegration


class SigmaIntegrationRead(BaseModel):
    """
    The Sigma connection, as the interface is allowed to see it.

    ``configured`` replaces the token: the screen needs to show whether one is saved,
    and never needs its value. A response that carried it would put an integration
    token into every browser cache and log along the way.
    """

    configured: bool
    account_id: int | None
    last_import_at: datetime | None
    last_status: ImportStatus | None
    last_message: str | None

    @classmethod
    def of(cls, integration: SigmaIntegration) -> "SigmaIntegrationRead":
        return cls(
            configured=integration.configured,
            account_id=integration.account_id,
            last_import_at=integration.last_import_at,
            last_status=integration.last_status,
            last_message=integration.last_message,
        )


class SigmaSettingsUpdate(BaseModel):
    token: str | None = Field(default=None, max_length=2048, repr=False)
    """Vazio mantém o token guardado — a tela não tem como reenviar o que não lê."""
    account_id: int | None = Field(default=None, ge=1)


class SigmaAccountRead(BaseModel):
    """An account the token can see, for choosing one instead of typing a number."""

    id: int
    name: str | None
    code: str | None


class SigmaImportRead(BaseModel):
    status: ImportStatus
    message: str
    read: int
    updated: int
    unmatched: list[str]
