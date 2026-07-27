import unittest

import httpx

from app.hikvision.exceptions import HikvisionAuthenticationError, HikvisionProtocolError
from app.hikvision.session import IsapiSession


class ExpiringNonceDevice:
    """Answers a fixed number of requests per handshake, then reports the nonce stale.

    This is the behaviour that made naive polling fail against the DS-K1T342: the
    terminal stops honouring a nonce after a while and answers ``401`` until the
    client performs a new Digest handshake.
    """

    def __init__(
        self, requests_per_handshake: int = 2, *, always_unauthorized: bool = False,
        drops_connection: bool = False,
    ) -> None:
        self.requests_per_handshake = requests_per_handshake
        self.always_unauthorized = always_unauthorized
        self.drops_connection = drops_connection
        self.handshakes = 0
        self.requests_since_handshake = 0
        self.served = 0

    def start_handshake(self) -> None:
        self.handshakes += 1
        self.requests_since_handshake = 0

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests_since_handshake += 1
        expired = self.requests_since_handshake > self.requests_per_handshake
        if expired and self.drops_connection:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.")
        if self.always_unauthorized or expired:
            return httpx.Response(401, text="<userCheck><statusValue>401</statusValue></userCheck>")
        self.served += 1
        return httpx.Response(200, json={"AcsEvent": {"totalMatches": 0}})


class SessionAgainstDevice(IsapiSession):
    def __init__(self, device: ExpiringNonceDevice) -> None:
        super().__init__(base_url="http://device:80", username="admin", password="secret")
        self._device = device

    def _build_client(self) -> httpx.AsyncClient:
        self._device.start_handshake()
        return httpx.AsyncClient(transport=httpx.MockTransport(self._device.handle))


class IsapiSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_renews_the_handshake_when_the_nonce_expires(self) -> None:
        device = ExpiringNonceDevice(requests_per_handshake=2)
        session = SessionAgainstDevice(device)
        await session.open()

        for _ in range(6):
            self.assertEqual(await session.post_json("/journal", {}), {"AcsEvent": {"totalMatches": 0}})

        self.assertEqual(device.served, 6)
        self.assertGreater(device.handshakes, 1)
        await session.close()

    async def test_retries_when_the_device_dropped_the_pooled_connection(self) -> None:
        device = ExpiringNonceDevice(requests_per_handshake=2, drops_connection=True)
        session = SessionAgainstDevice(device)
        await session.open()

        for _ in range(6):
            self.assertEqual(await session.post_json("/journal", {}), {"AcsEvent": {"totalMatches": 0}})

        self.assertEqual(device.served, 6)
        await session.close()

    async def test_reports_refused_credentials_after_renewing(self) -> None:
        session = SessionAgainstDevice(ExpiringNonceDevice(always_unauthorized=True))
        await session.open()

        with self.assertRaises(HikvisionAuthenticationError):
            await session.post_json("/journal", {})

        await session.close()

    async def test_rejects_requests_before_the_session_is_open(self) -> None:
        session = SessionAgainstDevice(ExpiringNonceDevice())

        with self.assertRaises(HikvisionProtocolError):
            await session.post_json("/journal", {})

    async def test_rejects_the_xml_fault_returned_by_json_endpoints(self) -> None:
        device = ExpiringNonceDevice()
        session = SessionAgainstDevice(device)
        device.handle = lambda request: httpx.Response(200, text="<ResponseStatus/>")
        await session.open()

        with self.assertRaises(HikvisionProtocolError):
            await session.post_json("/journal", {})

        await session.close()
