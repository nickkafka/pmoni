import unittest
from datetime import datetime

from app.hikvision.acs_event import AcsEventParser
from app.hikvision.exceptions import HikvisionEventParseError


def journal_entry(**overrides):
    entry = {
        "major": 5,
        "minor": 75,
        "time": "2026-07-27T14:17:00-03:00",
        "name": "nk",
        "employeeNoString": "2",
        "serialNo": 261143,
        "currentVerifyMode": "cardOrFaceOrFp",
    }
    entry.update(overrides)
    return entry


class AcsEventParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = AcsEventParser()

    def test_parses_identified_access(self) -> None:
        event = self.parser.parse(journal_entry(), device_id=3)

        assert event is not None
        self.assertEqual(event.external_id, "261143")
        self.assertEqual(event.device_id, 3)
        self.assertEqual(event.employee_no, "2")
        self.assertEqual(event.access_type, "cardOrFaceOrFp")
        self.assertTrue(event.success)
        self.assertEqual(event.event_time, datetime.fromisoformat("2026-07-27T14:17:00-03:00"))

    def test_ignores_door_hardware_entry_without_person(self) -> None:
        entry = journal_entry(minor=21, employeeNoString=None, name=None)

        self.assertIsNone(self.parser.parse(entry, device_id=3))

    def test_reports_unlisted_code_as_denied_access(self) -> None:
        event = self.parser.parse(journal_entry(minor=76), device_id=3)

        assert event is not None
        self.assertFalse(event.success)

    def test_keeps_presentation_data_out_of_the_domain_event(self) -> None:
        event = self.parser.parse(journal_entry(), device_id=3)

        self.assertNotIn("nk", str(event))

    def test_rejects_entry_without_timestamp(self) -> None:
        with self.assertRaises(HikvisionEventParseError):
            self.parser.parse(journal_entry(time=None), device_id=3)

    def test_rejects_entry_without_serial_number(self) -> None:
        with self.assertRaises(HikvisionEventParseError):
            self.parser.parse(journal_entry(serialNo=None), device_id=3)
