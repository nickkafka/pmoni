"""
Reading residents out of Sigma Cloud.

Only ``GET``: pMoni copies from Sigma and never writes back. Sigma is the register
of record for who lives where, and a bug here must not be able to change it.

Shapes worth knowing, measured against the real API on 2026-08-14:

- ``commonEnroll`` is the number the facials report as ``employeeNo``. Of the 49
  identifiers in the real register it matched all 49, while ``id`` matched none.
- ``federalRegister`` is the CPF and ``nationalId`` is the RG.
- ``unities`` is a list, and everyone measured had exactly one. Nobody had two, so
  the first is taken and the rest ignored rather than guessed at.
- ``/v1/.../dwellers`` answers a plain list; ``/v5`` answers a paginated envelope.
  v1 is used because one request returns everyone.
"""

from typing import Any

import httpx

from app.domain.entities.sigma import SigmaDweller

BASE_URL = "https://api.segware.com.br"
TIMEOUT_SECONDS = 45.0


class SigmaUnavailable(RuntimeError):
    """Sigma refused or could not be reached, with a reason worth showing."""


class SigmaClient:
    def __init__(self, token: str, *, base_url: str = BASE_URL, timeout: float = TIMEOUT_SECONDS) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=timeout,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def accounts(self) -> list[dict[str, Any]]:
        """Every account the token can see, for the operator to pick theirs."""
        payload = await self._get("/v1/accounts")
        return payload if isinstance(payload, list) else payload.get("content", [])

    async def dwellers(self, account_id: int) -> list[SigmaDweller]:
        payload = await self._get(f"/v1/accounts/{account_id}/dwellers")
        registros = payload if isinstance(payload, list) else payload.get("content", [])
        return [self._to_dweller(registro) for registro in registros if _enrollment_of(registro)]

    async def _get(self, path: str) -> Any:
        try:
            response = await self._client.get(path)
        except httpx.HTTPError as exc:
            raise SigmaUnavailable(f"Não foi possível falar com o Sigma: {exc}") from exc

        if response.status_code == httpx.codes.UNAUTHORIZED:
            raise SigmaUnavailable("O Sigma recusou o token. Verifique se ele ainda é válido.")
        if response.status_code == httpx.codes.FORBIDDEN:
            raise SigmaUnavailable(
                "O token não tem permissão para ler moradores. Peça à Segware que "
                "libere essa leitura para o usuário de integração."
            )
        if response.status_code >= httpx.codes.BAD_REQUEST:
            raise SigmaUnavailable(f"O Sigma respondeu HTTP {response.status_code} em {path}.")
        try:
            return response.json()
        except ValueError as exc:
            raise SigmaUnavailable(f"O Sigma não respondeu em JSON em {path}.") from exc

    @staticmethod
    def _to_dweller(registro: dict[str, Any]) -> SigmaDweller:
        unidades = registro.get("unities") or []
        primeira = unidades[0] if isinstance(unidades, list) and unidades else {}
        return SigmaDweller(
            enrollment=_enrollment_of(registro),
            name=str(registro.get("name") or "").strip(),
            apartment=_clean(primeira.get("unit")),
            block=_clean(primeira.get("block")),
            cpf=_clean(registro.get("federalRegister")),
            rg=_clean(registro.get("nationalId")),
        )


def _enrollment_of(registro: dict[str, Any]) -> str:
    value = registro.get("commonEnroll")
    return "" if value is None else str(value).strip()


def _clean(value: Any) -> str | None:
    """An empty string from Sigma means "not filled in", not "set it to blank"."""
    text = str(value).strip() if value is not None else ""
    return text or None
