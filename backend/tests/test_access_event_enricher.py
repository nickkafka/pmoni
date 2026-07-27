import asyncio
import unittest
from datetime import UTC, datetime

from app.application.ports.device_lookup import DeviceLookup
from app.application.ports.resident_lookup import ResidentLookup
from app.application.services.access_event_enricher import AccessEventEnricher
from app.domain.entities.access_event import AccessEvent, DeviceSummary
from app.domain.entities.resident import ResidentSummary


def access_event(employee_no: str | None = "2") -> AccessEvent:
    return AccessEvent("261143", 1, employee_no, "face", True, datetime(2026, 7, 27, tzinfo=UTC))


class FakeLookup(ResidentLookup):
    def __init__(self, residents: dict[str, ResidentSummary], *, broken: bool = False) -> None:
        self.residents = residents
        self.broken = broken
        self.queries: list[str] = []

    def find(self, employee_no: str) -> ResidentSummary | None:
        self.queries.append(employee_no)
        if self.broken:
            raise RuntimeError("banco indisponível")
        return self.residents.get(employee_no)


class FakeDeviceManager:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[AccessEvent] = asyncio.Queue()
        self.unsubscribed = False

    def subscribe(self, *, max_queue_size: int = 100) -> asyncio.Queue[AccessEvent]:
        return self.queue

    def unsubscribe(self, queue: asyncio.Queue[AccessEvent]) -> None:
        self.unsubscribed = True


class FakeDeviceLookup(DeviceLookup):
    def __init__(self, devices: dict[int, str], *, broken: bool = False) -> None:
        self.devices = devices
        self.broken = broken

    def find(self, device_id: int) -> DeviceSummary | None:
        if self.broken:
            raise RuntimeError("banco indisponível")
        name = self.devices.get(device_id)
        return DeviceSummary(device_id, name) if name else None


RESIDENT = ResidentSummary(52, "2", "nk", "301", "A", True)


class AccessEventEnricherTests(unittest.IsolatedAsyncioTestCase):
    async def enrich(self, event: AccessEvent, lookup: FakeLookup, devices: FakeDeviceLookup | None = None):
        manager = FakeDeviceManager()
        enricher = AccessEventEnricher(manager, lookup, devices)
        await enricher.start()
        subscription = enricher.subscribe()
        try:
            manager.queue.put_nowait(event)
            return await asyncio.wait_for(subscription.get(), timeout=1)
        finally:
            await enricher.stop()

    async def test_attaches_the_resident_to_the_event(self) -> None:
        enriched = await self.enrich(access_event(), FakeLookup({"2": RESIDENT}))

        self.assertEqual(enriched.event.external_id, "261143")
        assert enriched.resident is not None
        self.assertEqual(enriched.resident.name, "nk")
        self.assertEqual(enriched.resident.apartment, "301")

    async def test_publishes_an_unknown_person_without_resident(self) -> None:
        enriched = await self.enrich(access_event("999"), FakeLookup({"2": RESIDENT}))

        self.assertIsNone(enriched.resident)
        self.assertEqual(enriched.event.employee_no, "999")

    async def test_publishes_the_event_when_the_lookup_fails(self) -> None:
        enriched = await self.enrich(access_event(), FakeLookup({}, broken=True))

        self.assertIsNone(enriched.resident)
        self.assertEqual(enriched.event.external_id, "261143")

    async def test_does_not_query_for_an_event_without_identifier(self) -> None:
        lookup = FakeLookup({})

        enriched = await self.enrich(access_event(None), lookup)

        self.assertIsNone(enriched.resident)
        self.assertEqual(lookup.queries, [])

    async def test_keeps_running_after_a_failed_lookup(self) -> None:
        manager = FakeDeviceManager()
        lookup = FakeLookup({"2": RESIDENT}, broken=True)
        enricher = AccessEventEnricher(manager, lookup)
        await enricher.start()
        subscription = enricher.subscribe()
        try:
            manager.queue.put_nowait(access_event())
            await asyncio.wait_for(subscription.get(), timeout=1)
            lookup.broken = False
            manager.queue.put_nowait(access_event())

            enriched = await asyncio.wait_for(subscription.get(), timeout=1)

            assert enriched.resident is not None
            self.assertEqual(enriched.resident.name, "nk")
        finally:
            await enricher.stop()

    async def test_names_the_device_the_event_came_from(self) -> None:
        enriched = await self.enrich(
            access_event(), FakeLookup({"2": RESIDENT}), FakeDeviceLookup({1: "Portaria social"})
        )

        assert enriched.device is not None
        self.assertEqual(enriched.device.name, "Portaria social")

    async def test_publishes_the_event_when_the_device_lookup_fails(self) -> None:
        enriched = await self.enrich(
            access_event(), FakeLookup({"2": RESIDENT}), FakeDeviceLookup({}, broken=True)
        )

        self.assertIsNone(enriched.device)
        assert enriched.resident is not None

    async def test_stop_releases_the_device_subscription(self) -> None:
        manager = FakeDeviceManager()
        enricher = AccessEventEnricher(manager, FakeLookup({}))
        await enricher.start()

        await enricher.stop()

        self.assertTrue(manager.unsubscribed)
