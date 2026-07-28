import asyncio
import unittest
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.entities.access_event import AccessEvent, EnrichedAccessEvent
from app.domain.entities.resident import ResidentSummary
from app.websocket.access_events import router


def passage(serial: str, name: str) -> EnrichedAccessEvent:
    event = AccessEvent(serial, 1, "2", "face", True, datetime(2026, 7, 28, tzinfo=UTC))
    return EnrichedAccessEvent(event, ResidentSummary(9, "2", name, "301", "A", True))


class FakeEnricher:
    def __init__(self, remembered: list[EnrichedAccessEvent]) -> None:
        self.remembered = remembered
        self.queue: asyncio.Queue[EnrichedAccessEvent] = asyncio.Queue()
        self.released = False

    def recent(self):
        return tuple(self.remembered)

    def subscribe(self, *, max_queue_size: int = 100):
        return self.queue

    def unsubscribe(self, queue) -> None:
        self.released = True


def build(enricher: FakeEnricher | None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.access_events = enricher
    return app


class AccessEventsEndpointTests(unittest.TestCase):
    def test_replays_recent_passages_to_a_screen_that_just_opened(self) -> None:
        enricher = FakeEnricher([passage("1", "nk"), passage("2", "Janaina")])

        with TestClient(build(enricher)).websocket_connect("/ws/access-events") as socket:
            first = socket.receive_json()
            second = socket.receive_json()

        self.assertEqual(first["data"]["resident"]["name"], "nk")
        self.assertEqual(second["data"]["resident"]["name"], "Janaina")

    def test_streams_a_passage_that_happens_while_connected(self) -> None:
        enricher = FakeEnricher([])

        with TestClient(build(enricher)).websocket_connect("/ws/access-events") as socket:
            enricher.queue.put_nowait(passage("7", "Beatriz"))
            message = socket.receive_json()

        self.assertEqual(message["type"], "access_event")
        self.assertEqual(message["data"]["external_id"], "7")

    def test_reports_that_monitoring_was_never_configured(self) -> None:
        with TestClient(build(None)).websocket_connect("/ws/access-events") as socket:
            message = socket.receive_json()

        self.assertEqual(message, {"type": "system_status", "status": "monitoring_unavailable"})

    def test_releases_the_subscription_when_the_screen_closes(self) -> None:
        enricher = FakeEnricher([passage("1", "nk")])

        with TestClient(build(enricher)).websocket_connect("/ws/access-events") as socket:
            socket.receive_json()

        self.assertTrue(enricher.released)
