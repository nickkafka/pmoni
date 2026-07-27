import asyncio
from contextlib import suppress

from app.application.ports.device_lookup import DeviceLookup
from app.application.ports.resident_lookup import ResidentLookup
from app.application.services.device_manager import DeviceManager
from app.application.services.event_broadcaster import EventBroadcaster
from app.core.logger import logger
from app.domain.entities.access_event import AccessEvent, DeviceSummary, EnrichedAccessEvent
from app.domain.entities.resident import ResidentSummary


class AccessEventEnricher:
    """Attaches local resident data to device events before the interface sees them.

    It consumes the manufacturer-neutral stream published by the ``DeviceManager``
    and republishes it enriched, so the WebSocket endpoint keeps away from the
    database and the device adapters keep away from presentation data.
    """

    def __init__(
        self, device_manager: DeviceManager, resident_lookup: ResidentLookup,
        device_lookup: DeviceLookup | None = None,
    ) -> None:
        self._device_manager = device_manager
        self._resident_lookup = resident_lookup
        self._device_lookup = device_lookup
        self._broadcaster: EventBroadcaster[EnrichedAccessEvent] = EventBroadcaster()
        self._subscription: asyncio.Queue[AccessEvent] | None = None
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        self._subscription = self._device_manager.subscribe()
        self._task = asyncio.create_task(self._run(), name="access-event-enricher")
        logger.info("Enriquecimento de eventos iniciado.")

    async def stop(self) -> None:
        task, subscription = self._task, self._subscription
        self._task, self._subscription = None, None
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        if subscription is not None:
            self._device_manager.unsubscribe(subscription)
        logger.info("Enriquecimento de eventos finalizado.")

    def subscribe(self, *, max_queue_size: int = 100) -> asyncio.Queue[EnrichedAccessEvent]:
        return self._broadcaster.subscribe(max_queue_size=max_queue_size)

    def unsubscribe(self, queue: asyncio.Queue[EnrichedAccessEvent]) -> None:
        self._broadcaster.unsubscribe(queue)

    async def _run(self) -> None:
        assert self._subscription is not None
        while True:
            event = await self._subscription.get()
            self._broadcaster.publish(self._enrich(event))

    def _enrich(self, event: AccessEvent) -> EnrichedAccessEvent:
        """Publish the event even when the resident is unknown or the lookup fails."""
        return EnrichedAccessEvent(event, self._resident_of(event), self._device_of(event))

    def _resident_of(self, event: AccessEvent) -> ResidentSummary | None:
        if not event.employee_no:
            return None
        try:
            resident = self._resident_lookup.find(event.employee_no)
        except Exception:
            logger.exception("Falha ao identificar a matrícula {}.", event.employee_no)
            return None
        if resident is None:
            logger.warning("Matrícula {} não está no cadastro local.", event.employee_no)
        return resident

    def _device_of(self, event: AccessEvent) -> DeviceSummary | None:
        if self._device_lookup is None:
            return None
        try:
            return self._device_lookup.find(event.device_id)
        except Exception:
            logger.exception("Falha ao identificar o dispositivo {}.", event.device_id)
            return None
