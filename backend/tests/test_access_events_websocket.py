from datetime import UTC, datetime
import unittest

from app.domain.entities.access_event import AccessEvent, DeviceSummary, EnrichedAccessEvent
from app.domain.entities.resident import ResidentSummary
from app.websocket.access_events import _event_message

EVENT = AccessEvent("evt-1", 5, "SIGMA-42", "face", True, datetime(2026, 7, 24, tzinfo=UTC))


class AccessEventWebSocketTests(unittest.TestCase):
    def test_serializes_normalized_event(self) -> None:
        message = _event_message(EnrichedAccessEvent(EVENT, None))

        self.assertEqual(message["type"], "access_event")
        self.assertEqual(message["data"]["employee_no"], "SIGMA-42")
        self.assertEqual(message["data"]["event_time"], "2026-07-24T00:00:00+00:00")

    def test_carries_the_resident_the_porter_has_to_read(self) -> None:
        resident = ResidentSummary(52, "SIGMA-42", "nk", "301", "A", True)

        message = _event_message(EnrichedAccessEvent(EVENT, resident))["data"]["resident"]

        assert message is not None
        self.assertEqual(message["name"], "nk")
        self.assertEqual(message["apartment"], "301")
        self.assertEqual(message["block"], "A")
        self.assertEqual(message["photo_url"], "/residents/52/photo")

    def test_reports_an_unknown_person_as_a_null_resident(self) -> None:
        self.assertIsNone(_event_message(EnrichedAccessEvent(EVENT, None))["data"]["resident"])

    def test_points_the_capture_at_the_copy_the_backend_kept(self) -> None:
        event = AccessEvent(
            "261143", 2, "42", "face", True, datetime(2026, 7, 28, tzinfo=UTC),
            snapshot="/LOCALS/pic/acsLinkCap/28_091059.jpeg",
        )

        message = _event_message(EnrichedAccessEvent(event, None))["data"]

        self.assertEqual(message["snapshot_url"], "/access-events/2/261143/snapshot")

    def test_omits_the_capture_when_the_device_did_not_take_one(self) -> None:
        self.assertIsNone(_event_message(EnrichedAccessEvent(EVENT, None))["data"]["snapshot_url"])

    def test_names_the_device_the_person_walked_through(self) -> None:
        enriched = EnrichedAccessEvent(EVENT, None, DeviceSummary(5, "Portaria social"))

        message = _event_message(enriched)["data"]["device"]

        self.assertEqual(message, {"id": 5, "name": "Portaria social"})

    def test_reports_an_unresolved_device_as_null(self) -> None:
        self.assertIsNone(_event_message(EnrichedAccessEvent(EVENT, None))["data"]["device"])

    def test_omits_the_photo_url_when_no_photo_was_synced(self) -> None:
        resident = ResidentSummary(52, "SIGMA-42", "nk", "301", "A", False)

        message = _event_message(EnrichedAccessEvent(EVENT, resident))["data"]["resident"]

        assert message is not None
        self.assertIsNone(message["photo_url"])
