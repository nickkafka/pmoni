from datetime import datetime
from ipaddress import ip_address
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_HOSTNAME_LABEL_LIMIT = 63


def _is_hostname_label(label: str) -> bool:
    return (
        0 < len(label) <= _HOSTNAME_LABEL_LIMIT
        and not label.startswith("-")
        and not label.endswith("-")
        and all(character.isalnum() or character == "-" for character in label)
    )


def validate_host(host: str) -> str:
    """Devices are often reached through a DDNS name rather than a fixed address."""
    host = host.strip()
    try:
        return str(ip_address(host))
    except ValueError:
        pass
    if all(_is_hostname_label(label) for label in host.rstrip(".").split(".")):
        return host
    raise ValueError("Informe um endereço IP ou um nome de host válido.")


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=80, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256, repr=False)
    model: str | None = Field(default=None, max_length=50)

    _check_host = field_validator("host")(validate_host)


class DeviceUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=80, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=100)
    password: str | None = Field(default=None, max_length=256, repr=False)
    """Left empty when the operator is not changing the stored credential."""
    model: str | None = Field(default=None, max_length=50)
    enabled: bool = True

    _check_host = field_validator("host")(validate_host)


class DeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    host: str
    port: int
    username: str
    model: str | None
    enabled: bool


class DeviceExportItem(BaseModel):
    """One device in an exported file.

    No password. The whole credential design exists to keep device passwords out of
    readable storage — encrypted with a key that is never versioned — and a plain
    file in a downloads folder holding every gate's password would undo that. The
    import accepts one when it is given, so a file can be completed by hand.
    """

    model_config = ConfigDict(from_attributes=True)

    name: str
    host: str
    port: int
    username: str
    model: str | None
    enabled: bool


class DeviceExport(BaseModel):
    exported_at: datetime
    devices: list[DeviceExportItem]
    note: str = (
        "As senhas não são exportadas. Ao importar, informe 'password' nos "
        "equipamentos novos; nos que já existem, a senha guardada é mantida."
    )


class DeviceImportItem(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=80, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=100)
    password: str | None = Field(default=None, max_length=256, repr=False)
    """Obrigatória para um equipamento novo; nos existentes, mantém a guardada."""
    model: str | None = Field(default=None, max_length=50)
    enabled: bool = True

    _check_host = field_validator("host")(validate_host)


class DeviceImport(BaseModel):
    devices: list[DeviceImportItem]

    @model_validator(mode="before")
    @classmethod
    def accept_a_bare_list(cls, payload: Any) -> Any:
        """Take either the exported file or just the list of devices.

        Writing the file by hand is one of the reasons this exists, and demanding an
        envelope around a list serves nobody who is doing that.
        """
        if isinstance(payload, list):
            return {"devices": payload}
        return payload


class DeviceImportReport(BaseModel):
    created: int
    updated: int
    pending: list[DeviceExportItem]
    """
    Equipamentos novos que o arquivo trouxe sem senha.

    Não são um erro: o arquivo exportado nunca traz senhas, e exigir que alguém
    abrisse o JSON para digitá-las à mão era o que tornava a importação ruim de usar.
    Voltam para a interface pedir as senhas e reenviar.
    """
