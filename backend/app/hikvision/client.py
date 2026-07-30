import asyncio
import re
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, tzinfo
from typing import Any

from app.application.ports.device_client import DeviceClient
from app.application.ports.snapshot_store import SnapshotStore
from app.core.logger import logger
from app.domain.entities.access_event import AccessEvent
from app.hikvision.acs_event import AcsEventParser
from app.hikvision.exceptions import HikvisionEventParseError, HikvisionProtocolError
from app.hikvision.session import IsapiSession

_LOCAL_TIME_PATTERN = re.compile(r"<localTime>([^<]+)</localTime>")


class HikvisionClient(DeviceClient):
    """Streams access events by polling the ISAPI access-control journal.

    Access terminals such as the DS-K1T342 do not expose the alert stream used by
    cameras, so new entries are collected by their monotonic ``serialNo``: the cursor
    starts at the newest entry already recorded and only later ones reach the domain.
    """

    ACS_EVENT_PATH = "/ISAPI/AccessControl/AcsEvent?format=json"
    TIME_PATH = "/ISAPI/System/time"
    MAX_PAGE_SIZE = 30
    MAX_SERIAL_NO = 3_000_000_000

    # The firmware scans the journal by time, so the search cost grows with the
    # window: one day measured around 4s against a DS-K1T342 while ten minutes
    # measured around 1.4s. Polling therefore asks only for the span since the last
    # entry seen, widened by a margin that absorbs clock differences.
    WINDOW_MARGIN = timedelta(minutes=2)
    # Widening only while the journal looks empty keeps startup cheap on a busy
    # device and still finds the last entry on one that has been idle for months.
    BASELINE_LOOKBACKS = (
        timedelta(hours=1), timedelta(days=1), timedelta(days=30), timedelta(days=365),
    )

    def __init__(
        self, *, device_id: int, host: str, port: int, username: str, password: str,
        scheme: str = "http", timeout_seconds: float = 30.0, poll_interval_seconds: float = 1.0,
        parser: AcsEventParser | None = None, session: IsapiSession | None = None,
        snapshot_store: SnapshotStore | None = None,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("O intervalo de consulta deve ser maior que zero.")
        self._device_id = device_id
        self._poll_interval_seconds = poll_interval_seconds
        self._parser = parser or AcsEventParser()
        self._snapshot_store = snapshot_store
        self._session = session or IsapiSession(
            base_url=f"{scheme}://{host}:{port}", username=username, password=password,
            timeout_seconds=timeout_seconds,
        )
        self._cursor = 0
        self._timezone: tzinfo | None = None
        self._window_start: datetime | None = None

    @property
    def device_id(self) -> int:
        return self._device_id

    @property
    def is_connected(self) -> bool:
        return self._session.is_open

    async def connect(self) -> None:
        await self._session.open()
        try:
            self._timezone = await self._read_device_timezone()
            if self._cursor == 0:
                # Only the very first connection skips the journal history. A
                # reconnection keeps the cursor and the window, so whoever passed
                # while the device was unreachable is still delivered.
                self._cursor = await self._read_latest_serial_no()
            if self._window_start is None:
                self._window_start = self._device_now()
        except Exception:
            await self.disconnect()
            raise
        logger.info(
            "Journal do dispositivo {} conectado a partir do evento {}.",
            self._device_id, self._cursor,
        )

    async def disconnect(self) -> None:
        await self._session.close()

    async def events(self) -> AsyncIterator[AccessEvent]:
        if not self._session.is_open:
            raise HikvisionProtocolError("O journal ISAPI não foi conectado.")
        while True:
            await asyncio.sleep(self._poll_interval_seconds)
            for event in await self._collect_new_events():
                yield event

    async def _collect_new_events(self) -> list[AccessEvent]:
        """Page through every journal entry recorded after the cursor."""
        events: list[AccessEvent] = []
        polled_at = self._device_now()
        since = self._window_start or polled_at
        position, previous_cursor, newest_seen = 0, self._cursor, None
        while True:
            page = await self._search(
                since=since, position=position, begin_serial_no=previous_cursor + 1
            )
            entries = page.get("InfoList") or []
            if not entries:
                break
            for entry in entries:
                self._cursor = max(self._cursor, self._serial_no_of(entry))
                newest_seen = self._entry_time(entry) or newest_seen
                event = self._parse(entry)
                if event is not None:
                    await self._keep_snapshot(event)
                    events.append(event)
            position += len(entries)
            if page.get("responseStatusStrg") != "MORE":
                break
        # Nothing before this poll can still be pending: the search just covered that
        # span and returned everything in it, so the window may close behind us.
        self._window_start = newest_seen or polled_at
        return events

    async def _keep_snapshot(self, event: AccessEvent) -> None:
        """Download the capture now, while the device still serves it.

        The published URL names an address only the device itself can be reached by,
        so the image is fetched through this session and kept for the interface.
        ``snapshot`` is cleared when that fails, since nothing would be there to show.
        """
        if self._snapshot_store is None or event.snapshot is None:
            return
        try:
            image = await self._session.get_bytes(event.snapshot)
        except Exception:
            logger.warning(
                "Não foi possível obter a captura do evento {} no dispositivo {}.",
                event.external_id, self._device_id,
            )
            event.snapshot = None
            return
        if image:
            self._snapshot_store.put(self._device_id, event.external_id, image)
        else:
            event.snapshot = None

    def _parse(self, entry: dict[str, Any]) -> AccessEvent | None:
        """Drop a malformed entry instead of interrupting the journal."""
        try:
            return self._parser.parse(entry, self._device_id)
        except HikvisionEventParseError:
            logger.warning(
                "Entrada inválida descartada no journal do dispositivo {}.", self._device_id
            )
            return None

    async def _read_latest_serial_no(self) -> int:
        """Baseline the cursor on the newest entry without paging the whole journal.

        Any window ending now that contains an entry also contains the newest one, so
        the search starts narrow and only widens while it comes back empty.
        """
        for lookback in self.BASELINE_LOOKBACKS:
            since = self._device_now() - lookback
            total = int((await self._search(since=since, position=0, page_size=1)).get("totalMatches") or 0)
            if total <= 0:
                continue
            page = await self._search(since=since, position=total - 1, page_size=1)
            serial = max((self._serial_no_of(entry) for entry in page.get("InfoList") or []), default=0)
            if serial:
                return serial
        return 0

    async def _search(
        self, *, since: datetime, position: int, page_size: int | None = None,
        begin_serial_no: int | None = None,
    ) -> dict[str, Any]:
        start_time, end_time = self._search_window(since)
        condition: dict[str, Any] = {
            "searchID": f"pmoni-{self._device_id}",
            "searchResultPosition": position,
            "maxResults": page_size or self.MAX_PAGE_SIZE,
            "major": 0,
            "minor": 0,
            "startTime": start_time,
            "endTime": end_time,
            "picEnable": True,
        }
        if begin_serial_no is not None:
            condition["beginSerialNo"] = begin_serial_no
            condition["endSerialNo"] = self.MAX_SERIAL_NO
        payload = await self._session.post_json(self.ACS_EVENT_PATH, {"AcsEventCond": condition})
        result = payload.get("AcsEvent")
        if not isinstance(result, dict):
            raise HikvisionProtocolError("Resposta do journal ISAPI sem AcsEvent.")
        return result

    def _search_window(self, since: datetime) -> tuple[str, str]:
        """Bound the query; the serial cursor is what actually selects new entries.

        The firmware rejects timestamps carrying microseconds, so they are dropped.
        """
        start = since - self.WINDOW_MARGIN
        end = self._device_now() + self.WINDOW_MARGIN
        return start.isoformat(), end.isoformat()

    def _device_now(self) -> datetime:
        return datetime.now(self._timezone).replace(microsecond=0)

    async def _read_device_timezone(self) -> tzinfo | None:
        """Anchor queries on the device clock so its offset drives the search window."""
        match = _LOCAL_TIME_PATTERN.search(await self._session.get_text(self.TIME_PATH))
        if match is None:
            raise HikvisionProtocolError("O dispositivo não informou o horário local.")
        try:
            return datetime.fromisoformat(match.group(1).strip()).tzinfo
        except ValueError as exc:
            raise HikvisionProtocolError("Horário local do dispositivo inválido.") from exc

    @staticmethod
    def _entry_time(entry: dict[str, Any]) -> datetime | None:
        try:
            return datetime.fromisoformat(str(entry.get("time")).replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _serial_no_of(entry: dict[str, Any]) -> int:
        try:
            return int(entry.get("serialNo") or 0)
        except (TypeError, ValueError):
            return 0
