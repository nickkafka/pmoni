from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.automation import ImportStatus


@dataclass(frozen=True, slots=True)
class SigmaIntegration:
    """The Sigma connection as everything outside the backend may see it.

    There is no token here on purpose. An integration token opens the client's whole
    base in Sigma, and the interface never needs to read one back — only to know
    whether one is saved. Leaving it out of the type that travels means it cannot be
    leaked by someone later adding a field to a response.
    """

    configured: bool
    account_id: int | None = None
    last_import_at: datetime | None = None
    last_status: ImportStatus | None = None
    last_message: str | None = None


@dataclass(frozen=True, slots=True)
class SigmaDweller:
    """A person as Sigma knows them.

    ``enrollment`` is Sigma's ``commonEnroll``, which is what the facials report as
    ``employeeNo`` — measured against the real register, it matched every single one,
    while ``id`` matched none.
    """

    enrollment: str
    name: str
    apartment: str | None
    block: str | None
    cpf: str | None
    rg: str | None


@dataclass(frozen=True, slots=True)
class SigmaImportReport:
    """What an import did, in the terms the operator has to act on."""

    read: int
    """Pessoas lidas do Sigma."""
    updated: int
    """Pessoas cujos cadastros foram atualizados."""
    unmatched: list[str]
    """
    Estão no Sigma e não foram encontradas nas faciais.

    Ou a pessoa não está cadastrada em equipamento nenhum, ou o nome diverge entre os
    dois sistemas — casar só pelo identificador escreveria o endereço de uma pessoa
    no cadastro de outra (ADR 0010), então divergência de nome é motivo para não
    gravar, e para avisar.
    """
