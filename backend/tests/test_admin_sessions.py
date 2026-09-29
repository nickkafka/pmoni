import unittest
from datetime import timedelta

from app.application.services.admin_sessions import AdminSessions


def build(lifetime: timedelta = timedelta(minutes=30)) -> AdminSessions:
    return AdminSessions(username="prever", password="prever", lifetime=lifetime)


class AdminSessionsTests(unittest.TestCase):
    def test_opens_a_session_for_the_right_credentials(self) -> None:
        sessions = build()

        token = sessions.open("prever", "prever")

        assert token is not None
        self.assertTrue(sessions.holds(token))

    def test_refuses_a_wrong_password(self) -> None:
        self.assertIsNone(build().open("prever", "errada"))

    def test_refuses_an_unknown_user(self) -> None:
        self.assertIsNone(build().open("outro", "prever"))

    def test_does_not_hold_a_token_it_never_issued(self) -> None:
        self.assertFalse(build().holds("inventado"))

    def test_does_not_hold_nothing(self) -> None:
        self.assertFalse(build().holds(None))

    def test_issues_a_different_token_per_login(self) -> None:
        sessions = build()

        self.assertNotEqual(sessions.open("prever", "prever"), sessions.open("prever", "prever"))

    def test_drops_a_session_that_expired(self) -> None:
        sessions = build(lifetime=timedelta(seconds=-1))

        token = sessions.open("prever", "prever")

        self.assertFalse(sessions.holds(token))

    def test_using_the_session_keeps_it_alive(self) -> None:
        """Conta o tempo parado, não o tempo desde o login: não expira no meio do trabalho."""
        from datetime import UTC, datetime
        from unittest.mock import patch

        sessions = build(lifetime=timedelta(minutes=30))
        start = datetime(2026, 9, 28, 14, 0, tzinfo=UTC)
        with patch.object(AdminSessions, "_now", return_value=start):
            token = sessions.open("prever", "prever")
        with patch.object(AdminSessions, "_now", return_value=start + timedelta(minutes=25)):
            self.assertTrue(sessions.holds(token))
        with patch.object(AdminSessions, "_now", return_value=start + timedelta(minutes=50)):
            self.assertTrue(sessions.holds(token))
        with patch.object(AdminSessions, "_now", return_value=start + timedelta(minutes=81)):
            self.assertFalse(sessions.holds(token))

    def test_closing_ends_the_session(self) -> None:
        sessions = build()
        token = sessions.open("prever", "prever")

        sessions.close(token)

        self.assertFalse(sessions.holds(token))

    def test_closing_one_session_keeps_the_others(self) -> None:
        sessions = build()
        first, second = sessions.open("prever", "prever"), sessions.open("prever", "prever")

        sessions.close(first)

        self.assertTrue(sessions.holds(second))
