import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any

from app.domain.entities.access_event import AccessEvent
from app.hikvision.client import HikvisionClient

DEVICE_TZ = timezone(timedelta(hours=-3))


def device_time(offset_seconds: int = 0) -> str:
    moment = datetime.now(DEVICE_TZ).replace(microsecond=0) + timedelta(seconds=offset_seconds)
    return moment.isoformat()


def journal_entry(serial_no: int, *, employee_no: str | None = "2", **overrides: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "major": 5,
        "minor": 75,
        "time": device_time(),
        "employeeNoString": employee_no,
        "serialNo": serial_no,
        "currentVerifyMode": "cardOrFaceOrFp",
    }
    entry.update(overrides)
    return entry


class FakeIsapiSession:
    """Reproduces the serial filtering and paging of the ISAPI journal search."""

    def __init__(self, entries: list[dict[str, Any]]) -> None:
        self.entries = entries
        self.is_open = False
        self.conditions: list[dict[str, Any]] = []

    async def open(self) -> None:
        self.is_open = True

    async def close(self) -> None:
        self.is_open = False

    async def get_text(self, path: str) -> str:
        return "<Time><localTime>2026-07-27T14:27:03-03:00</localTime></Time>"

    async def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        condition = payload["AcsEventCond"]
        self.conditions.append(condition)
        begin = condition.get("beginSerialNo")
        matches = [
            e
            for e in self.entries
            if (begin is None or e["serialNo"] >= begin)
            and self._within(e, condition["startTime"], condition["endTime"])
        ]
        position, size = condition["searchResultPosition"], condition["maxResults"]
        page = matches[position : position + size]
        return {
            "AcsEvent": {
                "totalMatches": len(matches),
                "numOfMatches": len(page),
                "responseStatusStrg": "MORE" if position + len(page) < len(matches) else "OK",
                "InfoList": page,
            }
        }

    @staticmethod
    def _within(entry: dict[str, Any], start: str, end: str) -> bool:
        """A malformed timestamp still reaches the client, which is what rejects it."""
        moment = entry.get("time")
        return start <= moment <= end if isinstance(moment, str) else True


async def collect(client: HikvisionClient, count: int, timeout: float = 2.0) -> list[AccessEvent]:
    events: list[AccessEvent] = []
    stream = client.events()

    async def drain() -> None:
        async for event in stream:
            events.append(event)
            if len(events) >= count:
                return

    try:
        await asyncio.wait_for(drain(), timeout=timeout)
    finally:
        await stream.aclose()
    return events


class HikvisionClientTests(unittest.IsolatedAsyncioTestCase):
    def build(self, session: FakeIsapiSession) -> HikvisionClient:
        return HikvisionClient(
            device_id=3, host="device", port=80, username="admin", password="secret",
            poll_interval_seconds=0.01, session=session,
        )

    async def test_connect_baselines_cursor_on_the_newest_entry(self) -> None:
        session = FakeIsapiSession([journal_entry(serial) for serial in (10, 11, 12)])
        client = self.build(session)

        await client.connect()

        self.assertTrue(client.is_connected)
        with self.assertRaises(asyncio.TimeoutError):
            await collect(client, 1, timeout=0.2)

    async def test_yields_only_entries_recorded_after_connecting(self) -> None:
        session = FakeIsapiSession([journal_entry(10)])
        client = self.build(session)
        await client.connect()

        session.entries.append(journal_entry(11, employee_no="99"))
        events = await collect(client, 1)

        self.assertEqual([event.external_id for event in events], ["11"])
        self.assertEqual(events[0].employee_no, "99")

    async def test_pages_through_a_burst_larger_than_one_page(self) -> None:
        session = FakeIsapiSession([journal_entry(1)])
        client = self.build(session)
        await client.connect()

        session.entries.extend(journal_entry(serial) for serial in range(2, 42))
        events = await collect(client, 40)

        self.assertEqual(len(events), 40)
        self.assertEqual(events[-1].external_id, "41")

    async def test_skips_door_entries_that_identify_nobody(self) -> None:
        session = FakeIsapiSession([journal_entry(1)])
        client = self.build(session)
        await client.connect()

        session.entries.append(journal_entry(2, employee_no=None, minor=21))
        session.entries.append(journal_entry(3))
        events = await collect(client, 1)

        self.assertEqual([event.external_id for event in events], ["3"])

    async def test_keeps_polling_after_a_malformed_entry(self) -> None:
        session = FakeIsapiSession([journal_entry(1)])
        client = self.build(session)
        await client.connect()

        session.entries.append(journal_entry(2, time=None))
        session.entries.append(journal_entry(3))
        events = await collect(client, 1)

        self.assertEqual([event.external_id for event in events], ["3"])

    async def test_polls_a_narrow_window_instead_of_the_whole_day(self) -> None:
        session = FakeIsapiSession([journal_entry(1)])
        client = self.build(session)
        await client.connect()
        session.conditions.clear()

        with self.assertRaises(asyncio.TimeoutError):
            await collect(client, 1, timeout=0.2)

        polls = [c for c in session.conditions if "beginSerialNo" in c]
        self.assertTrue(polls)
        for condition in polls:
            span = datetime.fromisoformat(condition["endTime"]) - datetime.fromisoformat(
                condition["startTime"]
            )
            self.assertLess(span, timedelta(minutes=10))

    async def test_baseline_stays_narrow_on_a_busy_device(self) -> None:
        session = FakeIsapiSession([journal_entry(1)])
        client = self.build(session)

        await client.connect()

        widest = max(
            datetime.fromisoformat(c["endTime"]) - datetime.fromisoformat(c["startTime"])
            for c in session.conditions
        )
        self.assertLess(widest, timedelta(days=1))

    async def test_baseline_widens_until_it_finds_an_idle_journal(self) -> None:
        session = FakeIsapiSession([journal_entry(7, time=device_time(-60 * 60 * 24 * 20))])
        client = self.build(session)

        await client.connect()

        self.assertEqual(client._cursor, 7)
        widest = max(
            datetime.fromisoformat(c["endTime"]) - datetime.fromisoformat(c["startTime"])
            for c in session.conditions
        )
        self.assertGreater(widest, timedelta(days=20))

    async def test_window_reopens_to_cover_a_long_outage(self) -> None:
        session = FakeIsapiSession([journal_entry(10, time=device_time(-7200))])
        client = self.build(session)
        await client.connect()
        await client.disconnect()
        # Stands in for hours of elapsed polling, which the test cannot wait out.
        client._window_start = datetime.now(DEVICE_TZ).replace(microsecond=0) - timedelta(hours=3)

        # Someone passes while the device is unreachable.
        session.entries.append(journal_entry(11, employee_no="99", time=device_time(-3600)))
        await client.connect()
        events = await collect(client, 1)

        self.assertEqual([event.external_id for event in events], ["11"])

    async def test_searches_without_microseconds_which_the_firmware_rejects(self) -> None:
        session = FakeIsapiSession([journal_entry(1)])
        client = self.build(session)

        await client.connect()

        self.assertTrue(session.conditions)
        for condition in session.conditions:
            self.assertNotIn(".", condition["startTime"])
            self.assertNotIn(".", condition["endTime"])

    async def test_searches_in_the_timezone_reported_by_the_device(self) -> None:
        session = FakeIsapiSession([journal_entry(1)])
        client = self.build(session)

        await client.connect()

        self.assertTrue(session.conditions[0]["startTime"].endswith("-03:00"))

    async def test_reconnection_delivers_what_happened_during_the_outage(self) -> None:
        session = FakeIsapiSession([journal_entry(10)])
        client = self.build(session)
        await client.connect()
        await client.disconnect()

        session.entries.append(journal_entry(11, employee_no="99"))
        await client.connect()
        events = await collect(client, 1)

        self.assertEqual([event.external_id for event in events], ["11"])

    async def test_reconnection_does_not_replay_the_whole_journal(self) -> None:
        session = FakeIsapiSession([journal_entry(serial) for serial in (10, 11, 12)])
        client = self.build(session)
        await client.connect()
        await client.disconnect()

        await client.connect()

        with self.assertRaises(asyncio.TimeoutError):
            await collect(client, 1, timeout=0.2)

    async def test_disconnect_closes_the_session(self) -> None:
        session = FakeIsapiSession([journal_entry(1)])
        client = self.build(session)
        await client.connect()

        await client.disconnect()

        self.assertFalse(client.is_connected)
