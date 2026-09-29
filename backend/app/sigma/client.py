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
- ``/v1/.../dwellers`` answers a plain list, but only of people still enabled.
  ``/v5`` with ``showDisabled`` also brings the disabled ones — measured on
  2026-09-28, 486 against 426 — and those are exactly the people the facials still
  hold and nobody has a photo of anymore. It answers a paginated envelope that, on
  this account, fits everyone in one page.
- The list never fills ``photoUrl`` (0 of 486). The profile photo only comes from
  ``/v1/.../dwellers/{id}/photo``, as a pre-signed S3 link that refuses the request
  when our ``Authorization`` header goes along with it.
- Visitors and service providers are not in the dwellers list. ``/v4/.../guests``
  and ``/v4/.../serviceProviders`` with ``showDisabled`` bring them, in the same
  envelope. Most visitors have no ``commonEnroll``: they were never exported to a
  facial, so ``id`` is the only thing that recognises them from one import to the
  next.
- The access-device photo (``/v3/.../dwellers/{id}/devices``, ``facialImageUrl``)
  answers 403 to the integration token, so it is not used.
"""

from typing import Any

import httpx

from app.domain.entities.sigma import SigmaDweller

BASE_URL = "https://api.segware.com.br"
TIMEOUT_SECONDS = 45.0
PAGE_SIZE = 500
MAX_PAGES = 50
"""Um teto para o laço: uma resposta que sempre diga haver outra página não trava a rotina."""

IMAGE_SIGNATURES = (b"\xff\xd8\xff", b"\x89PNG")


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
        registros = await self._paged(f"/v5/accounts/{account_id}/dwellers")
        return [self._to_dweller(registro) for registro in registros if _enrollment_of(registro)]

    async def visitors(self, account_id: int) -> list[SigmaDweller]:
        """Visitors and service providers, enabled or not, with or without a facial."""
        pessoas: list[SigmaDweller] = []
        for kind in ("guests", "serviceProviders"):
            for registro in await self._paged(f"/v4/accounts/{account_id}/{kind}"):
                if isinstance(registro.get("id"), int):
                    pessoas.append(self._to_dweller(registro, visitor=True))
        return pessoas

    async def _paged(self, path: str) -> list[dict[str, Any]]:
        registros: list[dict[str, Any]] = []
        for page in range(MAX_PAGES):
            payload = await self._get(
                path, params={"showDisabled": "true", "page": page, "pageSize": PAGE_SIZE}
            )
            if isinstance(payload, list):
                return registros + payload
            registros.extend(payload.get("dwellers") or payload.get("content") or [])
            if not payload.get("hasNextPage"):
                break
        return registros

    async def profile_photo(self, account_id: int, dweller_id: int) -> bytes | None:
        """The person's profile photo, or ``None`` when Sigma keeps none.

        Anything that is not a JPEG or a PNG is treated as no photo: what lands here
        is shown to the porter as this person's face, and an S3 error page stored in
        its place would be a broken image on the one screen that must not have one.
        """
        payload = await self._get(f"/v1/accounts/{account_id}/dwellers/{dweller_id}/photo")
        url = payload.get("photoUrl") if isinstance(payload, dict) else None
        if not url:
            return None
        # O link já vem assinado; com o nosso Authorization junto, o S3 recusa.
        try:
            async with httpx.AsyncClient(timeout=self._client.timeout) as plain:
                response = await plain.get(url)
        except httpx.HTTPError as exc:
            raise SigmaUnavailable(f"Não foi possível baixar a foto do Sigma: {exc}") from exc
        if response.status_code != httpx.codes.OK:
            return None
        return response.content if response.content.startswith(IMAGE_SIGNATURES) else None

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            response = await self._client.get(path, params=params)
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
    def _to_dweller(registro: dict[str, Any], *, visitor: bool = False) -> SigmaDweller:
        unidades = registro.get("unities") or []
        primeira = unidades[0] if isinstance(unidades, list) and unidades else {}
        return SigmaDweller(
            enrollment=_enrollment_of(registro),
            name=str(registro.get("name") or "").strip(),
            apartment=_clean(primeira.get("unit")),
            block=_clean(primeira.get("block")),
            cpf=_clean(registro.get("federalRegister")),
            rg=_clean(registro.get("nationalId")),
            sigma_id=registro.get("id") if isinstance(registro.get("id"), int) else None,
            enabled=registro.get("enabled") is not False,
            visitor=visitor,
        )


def _enrollment_of(registro: dict[str, Any]) -> str:
    value = registro.get("commonEnroll")
    return "" if value is None else str(value).strip()


def _clean(value: Any) -> str | None:
    """An empty string from Sigma means "not filled in", not "set it to blank"."""
    text = str(value).strip() if value is not None else ""
    return text or None
