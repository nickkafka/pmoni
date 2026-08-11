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
    document: str | None
    has_photo: bool
    synced_at: datetime | None


class ResidentLocationUpdate(BaseModel):
    """Location typed against one enrollment.

    The document is deliberately absent: it identifies a person, not an enrollment,
    and is written through ``PersonDetailsUpdate`` so it cannot end up set on one
    gate and missing on another.
    """

    apartment: str | None = Field(default=None, max_length=32)
    block: str | None = Field(default=None, max_length=32)


class DirectoryPersonRead(BaseModel):
    """A person as the porter's search returns them, merged across enrollments."""

    model_config = ConfigDict(from_attributes=True)

    employee_no: str
    name: str
    apartment: str | None
    block: str | None
    document: str | None
    photo_id: int | None
    device_ids: list[int]
    device_names: list[str]


class PersonDetailsUpdate(BaseModel):
    """Everything an import knows about one person, addressed the way it knows them.

    Sigma delivers people, not enrollments, so this identifies them the same way the
    directory groups them: identifier plus name.

    A field left out of the request is left alone; a field sent as ``null`` is
    cleared. The difference matters at both ends: a partial import must not blank
    what it does not know, and an operator emptying a box means to empty it.
    """

    employee_no: str = Field(max_length=64)
    name: str = Field(max_length=128)
    apartment: str | None = Field(default=None, max_length=32)
    block: str | None = Field(default=None, max_length=32)
    document: str | None = Field(default=None, max_length=32)


class ResidentPurgeRead(BaseModel):
    removed: int


class ResidentSyncRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    created: int
    updated: int
    photos_downloaded: int
    removed: int
    without_photo: int
    failures: int
