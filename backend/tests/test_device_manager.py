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
        return [device for device in self.devices if device.enabled]

    def list_all(self) -> list[Device]:
        return list(self.devices)

    def update(self, device: Device, encrypted_credentials: str | None) -> Device | None:
        self.devices = [device if item.id == device.id else item for item in self.devices]
        return device

    def remove(self, device_id: int) -> bool:
        self.devices = [item for item in self.devices if item.id != device_id]
        return True


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
        self.created: list[Device] = []

    def create(self, device: Device) -> DeviceClient:
        assert device.id is not None
        self.created.append(device)
        return FakeClient(device.id, self.event)


def device(device_id: int, *, host: str = "192.168.1.10", enabled: bool = True) -> Device:
    return Device(device_id, f"Portaria {device_id}", host, 80, "admin", None, enabled)


async def wait_for_state(
    manager: DeviceManager, device_id: int, state: DeviceConnectionState, timeout: float = 1.0
) -> None:
    """Supervisors run as tasks, so their state settles after refresh returns."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        current = manager.statuses().get(device_id)
        if current is not None and current.state is state:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"Dispositivo {device_id} não alcançou {state}.")


class DeviceManagerTests(unittest.IsolatedAsyncioTestCase):
    def build(self, devices: list[Device]) -> tuple[DeviceManager, FakeRepository, FakeFactory]:
        repository = FakeRepository(devices)
        factory = FakeFactory(AccessEvent("evt-1", 1, "1001", "face", True, datetime.now()))
        return DeviceManager(repository, factory, reconnect_delay_seconds=0.01), repository, factory

    async def test_forwards_event_and_stops_client(self) -> None:
        manager, _, _ = self.build([device(1)])
        subscription = manager.subscribe()

        await manager.start()
        self.assertEqual((await asyncio.wait_for(subscription.get(), timeout=1)).external_id, "evt-1")
        self.assertEqual(manager.statuses()[1].state, DeviceConnectionState.CONNECTED)
        await manager.stop()
        self.assertEqual(manager.statuses()[1].state, DeviceConnectionState.STOPPED)

    async def test_adopts_a_device_registered_after_start(self) -> None:
        manager, repository, factory = self.build([device(1)])
        await manager.start()

        repository.devices.append(device(2))
        await manager.refresh()

        self.assertEqual(sorted(d.id for d in factory.created), [1, 2])
        await wait_for_state(manager, 2, DeviceConnectionState.CONNECTED)
        await manager.stop()

    async def test_drops_a_device_removed_from_the_registry(self) -> None:
        manager, repository, _ = self.build([device(1), device(2)])
        await manager.start()

        repository.remove(2)
        await manager.refresh()

        self.assertEqual(manager.statuses()[2].state, DeviceConnectionState.STOPPED)
        await wait_for_state(manager, 1, DeviceConnectionState.CONNECTED)
        await manager.stop()

    async def test_rebuilds_a_device_whose_address_changed(self) -> None:
        manager, repository, factory = self.build([device(1)])
        await manager.start()

        repository.update(device(1, host="10.0.0.9"), None)
        await manager.refresh()

        self.assertEqual([d.host for d in factory.created], ["192.168.1.10", "10.0.0.9"])
        await manager.stop()

    async def test_keeps_an_unchanged_device_running(self) -> None:
        manager, _, factory = self.build([device(1)])
        await manager.start()

        await manager.refresh()

        self.assertEqual(len(factory.created), 1)
        await manager.stop()

    async def test_rebuilds_a_device_whose_credential_changed(self) -> None:
        manager, _, factory = self.build([device(1)])
        await manager.start()

        await manager.refresh(restart=(1,))

        self.assertEqual(len(factory.created), 2)
        await manager.stop()

    async def test_stops_supervising_a_disabled_device(self) -> None:
        manager, repository, _ = self.build([device(1)])
        await manager.start()

        repository.update(device(1, enabled=False), None)
        await manager.refresh()

        self.assertEqual(manager.statuses()[1].state, DeviceConnectionState.STOPPED)
        await manager.stop()

    async def test_refresh_is_ignored_before_start(self) -> None:
        manager, _, factory = self.build([device(1)])

        await manager.refresh()

        self.assertEqual(factory.created, [])
