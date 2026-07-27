from ipaddress import ip_address

from pydantic import BaseModel, ConfigDict, Field, field_validator

_HOSTNAME_LABEL_LIMIT = 63


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=80, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256, repr=False)
    model: str | None = Field(default=None, max_length=50)

    @field_validator("host")
    @classmethod
    def accept_address_or_hostname(cls, host: str) -> str:
        """Devices are often reached through a DDNS name rather than a fixed address."""
        host = host.strip()
        try:
            return str(ip_address(host))
        except ValueError:
            pass
        labels = host.rstrip(".").split(".")
        if all(cls._is_hostname_label(label) for label in labels):
            return host
        raise ValueError("Informe um endereço IP ou um nome de host válido.")

    @staticmethod
    def _is_hostname_label(label: str) -> bool:
        return (
            0 < len(label) <= _HOSTNAME_LABEL_LIMIT
            and not label.startswith("-")
            and not label.endswith("-")
            and all(character.isalnum() or character == "-" for character in label)
        )


class DeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    host: str
    port: int
    username: str
    model: str | None
    enabled: bool
