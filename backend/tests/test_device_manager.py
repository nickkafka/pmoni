import asyncio
import unittest
from collections.abc import AsyncIterator
from datetime import datetime

from app.application.ports.device_client import DeviceClient
from app.application.ports.device_client_factory import DeviceClientFactory
from app.application.ports.device_repository import DeviceRepository
from app.application.services.device_manager import DeviceConnectionState, DeviceManager
from app.domain.entities.access_event import AccessEvent
from app.domain.entities.device import Device


class FakeRepository(DeviceRepository):
    def __init__(self, devices: list[Device]) -> None:
        self.devices = devices

    def add(self, device: Device, encrypted_credentials: str) -> Device:
        raise NotImplementedError

    def get(self, device_id: int) -> Device | None:
        return next((item for item in self.devices if item.id == device_id), None)

    def list_enabled(self) -> list[Device]:
        return self.devices


class FakeClient(DeviceClient):
    def __init__(self, device_id: int, event: AccessEvent) -> None:
        self._device_id, self._event, self._sent, self.connected = device_id, event, False, False

    @property
    def device_id(self) -> int:
        return self._device_id

    @property
    def is_connected(self) -> bool:
        return self.connected

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def events(self) -> AsyncIterator[AccessEvent]:
        if not self._sent:
            self._sent = True
            yield self._event
        await asyncio.sleep(60)


class FakeFactory(DeviceClientFactory):
    def __init__(self, event: AccessEvent) -> None:
        self.event = event

    def create(self, device: Device) -> DeviceClient:
        assert device.id is not None
        return FakeClient(device.id, self.event)


class DeviceManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_forwards_event_and_stops_client(self) -> None:
        device = Device(1, "Portaria", "192.168.1.10", 80, "admin", None, True)
        event = AccessEvent("evt-1", 1, "1001", "face", True, datetime.now())
        manager = DeviceManager(FakeRepository([device]), FakeFactory(event), reconnect_delay_seconds=0.01)
        subscription = manager.subscribe()

        await manager.start()
        self.assertEqual((await asyncio.wait_for(subscription.get(), timeout=1)).external_id, "evt-1")
        self.assertEqual(manager.statuses()[1].state, DeviceConnectionState.CONNECTED)
        await manager.stop()
        self.assertEqual(manager.statuses()[1].state, DeviceConnectionState.STOPPED)
