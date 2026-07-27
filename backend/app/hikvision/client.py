from collections.abc import AsyncIterator

import httpx

from app.application.ports.device_client import DeviceClient
from app.domain.entities.access_event import AccessEvent
from app.core.logger import logger
from app.hikvision.authentication import digest_auth
from app.hikvision.event_stream import iter_alert_payloads
from app.hikvision.exceptions import HikvisionAuthenticationError, HikvisionEventParseError, HikvisionProtocolError
from app.hikvision.parser import HikvisionAlertParser


class HikvisionClient(DeviceClient):
    ALERT_STREAM_PATH = "/ISAPI/Event/notification/alertStream"

    def __init__(
        self, *, device_id: int, host: str, port: int, username: str, password: str,
        scheme: str = "http", timeout_seconds: float = 20.0,
        parser: HikvisionAlertParser | None = None,
    ) -> None:
        self._device_id = device_id
        self._base_url = f"{scheme}://{host}:{port}"
        self._auth = digest_auth(username, password)
        self._timeout = httpx.Timeout(timeout_seconds, read=None)
        self._parser = parser or HikvisionAlertParser()
        self._http: httpx.AsyncClient | None = None
        self._stream_context = None
        self._response: httpx.Response | None = None

    @property
    def device_id(self) -> int:
        return self._device_id

    @property
    def is_connected(self) -> bool:
        return self._response is not None

    async def connect(self) -> None:
        if self._response is not None:
            return
        self._http = httpx.AsyncClient(auth=self._auth, timeout=self._timeout)
        self._stream_context = self._http.stream(
            "GET", f"{self._base_url}{self.ALERT_STREAM_PATH}",
            headers={"Accept": "multipart/mixed, application/xml, application/json"},
        )
        response = await self._stream_context.__aenter__()
        if response.status_code in {401, 403}:
            await self.disconnect()
            raise HikvisionAuthenticationError("Credenciais Hikvision recusadas pelo dispositivo.")
        if response.status_code != 200:
            status_code = response.status_code
            await self.disconnect()
            raise HikvisionProtocolError(f"Alert Stream respondeu HTTP {status_code}.")
        self._response = response

    async def disconnect(self) -> None:
        stream_context, http = self._stream_context, self._http
        self._stream_context, self._response, self._http = None, None, None
        if stream_context is not None:
            await stream_context.__aexit__(None, None, None)
        if http is not None:
            await http.aclose()

    async def events(self) -> AsyncIterator[AccessEvent]:
        if self._response is None:
            raise HikvisionProtocolError("O Alert Stream não foi conectado.")
        async for payload in iter_alert_payloads(self._response):
            try:
                event = self._parser.parse(payload, self.device_id)
            except HikvisionEventParseError:
                logger.warning("Notificação ISAPI inválida descartada no dispositivo {}.", self.device_id)
                continue
            if event is not None:
                yield event
