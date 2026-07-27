from datetime import UTC, datetime
import unittest

from app.domain.entities.access_event import AccessEvent
from app.websocket.access_events import _event_message


class AccessEventWebSocketTests(unittest.TestCase):
    def test_serializes_normalized_event(self) -> None:
        event = AccessEvent("evt-1", 5, "SIGMA-42", "face", True, datetime(2026, 7, 24, tzinfo=UTC))
        message = _event_message(event)
        self.assertEqual(message["type"], "access_event")
        self.assertEqual(message["data"]["employee_no"], "SIGMA-42")
        self.assertEqual(message["data"]["event_time"], "2026-07-24T00:00:00+00:00")
