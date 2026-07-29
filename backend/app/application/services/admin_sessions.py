import secrets
from datetime import UTC, datetime, timedelta


class AdminSessions:
    """Issues and validates the sessions that unlock the administration screen.

    Sessions live in memory only: restarting the application ends every one of
    them, which is the right default for a machine left in a guardhouse.
    """

    def __init__(self, *, username: str, password: str, lifetime: timedelta) -> None:
        self._username = username
        self._password = password
        self._lifetime = lifetime
        self._expiries: dict[str, datetime] = {}

    def open(self, username: str, password: str) -> str | None:
        """Return a token for the right credentials, or ``None`` for any other."""
        # Both are compared even when the username already failed, so the answer
        # takes the same time either way.
        correct_user = secrets.compare_digest(username, self._username)
        correct_password = secrets.compare_digest(password, self._password)
        if not (correct_user and correct_password):
            return None
        token = secrets.token_urlsafe(32)
        self._expiries[token] = self._now() + self._lifetime
        return token

    def holds(self, token: str | None) -> bool:
        if not token:
            return False
        expiry = self._expiries.get(token)
        if expiry is None:
            return False
        if expiry <= self._now():
            self._expiries.pop(token, None)
            return False
        return True

    def close(self, token: str | None) -> None:
        if token:
            self._expiries.pop(token, None)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)
