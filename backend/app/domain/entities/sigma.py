from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.automation import ImportStatus

SIGMA_PHOTO_PREFIX = "sigma:"
"""
Marca a foto que veio do perfil no Sigma, e não da facial.

Nunca coincide com a referência de um equipamento, então a sincronização troca essa
foto pela da facial assim que ela passar a ter uma.
"""


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
    sigma_id: int | None = None
    """Sigma's own ``id``, which is what its photo route is addressed by."""
    enabled: bool = True
    """Disabled in Sigma, and often still enrolled on a facial that lets them in."""
    visitor: bool = False
    """A visitor or service provider, rather than somebody living there."""


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
    photos: int = 0
    """Pessoas sem foto em facial nenhuma que ganharam a foto de perfil do Sigma."""
    inactive: int = 0
    """Desativadas no Sigma e ainda cadastradas em alguma facial."""
    visitors: "SigmaVisitorReport | None" = None
    """O que a importação fez com os visitantes que não estão em facial nenhuma."""


@dataclass(frozen=True, slots=True)
class SigmaVisitorReport:
    """Visitors active in Sigma and on no facial, as kept in pMoni's directory."""

    created: int
    updated: int
    removed: int
    photos: int
