import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from app.application.ports.device_client import DeviceClient
from app.application.ports.device_client_factory import DeviceClientFactory
from app.application.ports.device_repository import DeviceRepository
from app.core.logger import logger
from app.domain.entities.access_event import AccessEvent


class DeviceConnectionState(StrEnum):
    STOPPED = "stopped"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ManagedDeviceStatus:
    device_id: int
    state: DeviceConnectionState
    reconnect_attempts: int


class DeviceManager:
    """Supervises manufacturer-neutral device clients and fans out their events."""

    def __init__(
        self,
        device_repository: DeviceRepository,
        client_factory: DeviceClientFactory,
        *,
        reconnect_delay_seconds: float = 5.0,
    ) -> None:
        if reconnect_delay_seconds <= 0:
            raise ValueError("O intervalo de reconexão deve ser maior que zero.")
        self._repository = device_repository
        self._client_factory = client_factory
        self._reconnect_delay_seconds = reconnect_delay_seconds
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._states: dict[int, DeviceConnectionState] = {}
        self._reconnect_attempts: dict[int, int] = {}
        self._subscribers: set[asyncio.Queue[AccessEvent]] = set()
        self._running = False
        self._lifecycle_lock = asyncio.Lock()

    async def start(self) -> None:
        """Load enabled devices and start one isolated supervisor per device."""
        async with self._lifecycle_lock:
            if self._running:
                return
            self._running = True
            for device in self._repository.list_enabled():
                if device.id is None:
                    logger.warning("Dispositivo sem identificador foi ignorado: {}", device.name)
                    continue
                try:
                    client = self._client_factory.create(device)
                except Exception:
                    self._states[device.id] = DeviceConnectionState.ERROR
                    self._reconnect_attempts[device.id] = 0
                    logger.exception("Não foi possível preparar o dispositivo {}.", device.id)
                    continue
                self._states[device.id] = DeviceConnectionState.STOPPED
                self._reconnect_attempts[device.id] = 0
                self._tasks[device.id] = asyncio.create_task(
                    self._supervise(client), name=f"device-supervisor-{device.id}"
                )
        logger.info("DeviceManager iniciado com {} dispositivo(s).", len(self._tasks))

    async def stop(self) -> None:
        """Cancel all supervisors and close their clients without leaking tasks."""
        async with self._lifecycle_lock:
            if not self._running:
                return
            self._running = False
            tasks = list(self._tasks.values())
            self._tasks.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for device_id in self._states:
            self._states[device_id] = DeviceConnectionState.STOPPED
        logger.info("DeviceManager finalizado.")

    def subscribe(self, *, max_queue_size: int = 100) -> asyncio.Queue[AccessEvent]:
        if max_queue_size <= 0:
            raise ValueError("O tamanho da fila deve ser maior que zero.")
        queue: asyncio.Queue[AccessEvent] = asyncio.Queue(maxsize=max_queue_size)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[AccessEvent]) -> None:
        self._subscribers.discard(queue)

    def statuses(self) -> Mapping[int, ManagedDeviceStatus]:
        return {
            device_id: ManagedDeviceStatus(
                device_id=device_id,
                state=state,
                reconnect_attempts=self._reconnect_attempts.get(device_id, 0),
            )
            for device_id, state in self._states.items()
        }

    async def _supervise(self, client: DeviceClient) -> None:
        device_id = client.device_id
        while self._running:
            try:
                self._states[device_id] = (
                    DeviceConnectionState.CONNECTING
                    if self._reconnect_attempts[device_id] == 0
                    else DeviceConnectionState.RECONNECTING
                )
                await client.connect()
                self._states[device_id] = DeviceConnectionState.CONNECTED
                self._reconnect_attempts[device_id] = 0
                logger.info("Dispositivo {} conectado.", device_id)
                async for event in client.events():
                    if not self._running:
                        break
                    self._publish(event)
                if self._running:
                    raise ConnectionError("O fluxo de eventos foi encerrado.")
            except asyncio.CancelledError:
                raise
            except Exception:
                self._states[device_id] = DeviceConnectionState.ERROR
                self._reconnect_attempts[device_id] += 1
                logger.exception("Falha no dispositivo {}. Nova tentativa em {}s.", device_id, self._reconnect_delay_seconds)
                await asyncio.sleep(self._reconnect_delay_seconds)
            finally:
                await self._disconnect_safely(client)

    def _publish(self, event: AccessEvent) -> None:
        for queue in tuple(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    continue
                logger.warning("Fila de eventos cheia; evento antigo descartado.")
            queue.put_nowait(event)

    @staticmethod
    async def _disconnect_safely(client: DeviceClient) -> None:
        try:
            await client.disconnect()
        except Exception:
            logger.exception("Falha ao desconectar dispositivo {}.", client.device_id)
