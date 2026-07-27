import unittest

from app.hikvision.parser import HikvisionAlertParser


class HikvisionAlertParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = HikvisionAlertParser()

    def test_parses_access_controller_json(self) -> None:
        event = self.parser.parse(
            b'{"AccessControllerEvent":{"serialNo":17,"employeeNoString":"SIGMA-42","currentVerifyMode":"face","dateTime":"2026-07-24T10:15:00-03:00","eventState":"active"}}',
            device_id=3,
        )
        assert event is not None
        self.assertEqual(event.external_id, "17")
        self.assertEqual(event.employee_no, "SIGMA-42")
        self.assertTrue(event.success)
        self.assertEqual(event.access_type, "face")

    def test_ignores_heartbeat_xml(self) -> None:
        event = self.parser.parse(
            b'<EventNotificationAlert><eventType>videoloss</eventType><eventState>inactive</eventState></EventNotificationAlert>',
            device_id=3,
        )
        self.assertIsNone(event)
