import asyncio
import unittest
from typing import Any

from app.domain.entities.access_event import AccessEvent
from app.hikvision.client import HikvisionClient


def journal_entry(serial_no: int, *, employee_no: str | None = "2", **overrides: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "major": 5,
        "minor": 75,
        "time": "2026-07-27T14:17:00-03:00",
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
        matches = [e for e in self.entries if begin is None or e["serialNo"] >= begin]
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

    async def test_disconnect_closes_the_session(self) -> None:
        session = FakeIsapiSession([journal_entry(1)])
        client = self.build(session)
        await client.connect()

        await client.disconnect()

        self.assertFalse(client.is_connected)
