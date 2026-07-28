from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ResidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    employee_no: str
    name: str
    apartment: str | None
    block: str | None
    has_photo: bool
    synced_at: datetime | None


class ResidentLocationUpdate(BaseModel):
    """Location maintained inside Monikraft until Sigma supplies it."""

    apartment: str | None = Field(default=None, max_length=32)
    block: str | None = Field(default=None, max_length=32)


class ResidentSyncRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    created: int
    updated: int
    photos_downloaded: int
    removed: int
    failures: int
