from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    host: IPvAnyAddress
    port: int = Field(default=80, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256, repr=False)
    model: str | None = Field(default=None, max_length=50)


class DeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    host: str
    port: int
    username: str
    model: str | None
    enabled: bool
