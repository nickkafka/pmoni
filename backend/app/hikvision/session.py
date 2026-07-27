from typing import Any

import httpx

from app.hikvision.exceptions import HikvisionAuthenticationError, HikvisionProtocolError


class IsapiSession:
    """Authenticated ISAPI transport that survives Digest nonce expiry.

    Hikvision terminals invalidate the Digest nonce after roughly thirty seconds.
    ``httpx`` keeps signing later requests with the stale nonce and reports the
    resulting ``401`` as a final response, so every request is retried once against
    a freshly challenged client before the credentials are considered refused.
    """

    def __init__(
        self, *, base_url: str, username: str, password: str, timeout_seconds: float = 30.0
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._timeout = httpx.Timeout(timeout_seconds)
        self._client: httpx.AsyncClient | None = None

    @property
    def is_open(self) -> bool:
        return self._client is not None

    async def open(self) -> None:
        if self._client is None:
            self._client = self._build_client()

    async def close(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            await client.aclose()

    async def get_bytes(self, path: str) -> bytes:
        response = await self._request("GET", path)
        return response.content

    async def get_text(self, path: str) -> str:
        response = await self._request("GET", path)
        return response.text

    async def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._request("POST", path, json=payload)
        return self._decode_json(path, response)

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = await self._send(method, path, **kwargs)
        if response.status_code == httpx.codes.UNAUTHORIZED:
            await self._renew_authentication()
            response = await self._send(method, path, **kwargs)
        if response.status_code == httpx.codes.UNAUTHORIZED:
            raise HikvisionAuthenticationError("Credenciais recusadas pelo dispositivo.")
        if response.status_code >= httpx.codes.BAD_REQUEST:
            raise HikvisionProtocolError(f"ISAPI {path} respondeu HTTP {response.status_code}.")
        return response

    async def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if self._client is None:
            raise HikvisionProtocolError("A sessão ISAPI não foi aberta.")
        return await self._client.request(method, f"{self._base_url}{path}", **kwargs)

    async def _renew_authentication(self) -> None:
        """Force a new Digest challenge by replacing the client holding the stale nonce."""
        await self.close()
        self._client = self._build_client()

    def _build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            auth=httpx.DigestAuth(self._username, self._password), timeout=self._timeout
        )

    @staticmethod
    def _decode_json(path: str, response: httpx.Response) -> dict[str, Any]:
        """Reject the XML fault bodies the firmware returns even on JSON endpoints."""
        try:
            payload = response.json()
        except ValueError as exc:
            raise HikvisionProtocolError(f"ISAPI {path} não respondeu em JSON.") from exc
        if not isinstance(payload, dict):
            raise HikvisionProtocolError(f"ISAPI {path} respondeu um JSON inesperado.")
        return payload
