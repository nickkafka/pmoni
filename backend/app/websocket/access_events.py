import asyncio
from contextlib import suppress
from urllib.parse import quote

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.application.services.access_event_enricher import AccessEventEnricher
from app.domain.entities.access_event import AccessEvent, DeviceSummary, EnrichedAccessEvent
from app.domain.entities.resident import ResidentSummary

router = APIRouter()


@router.websocket("/ws/access-events")
async def access_events(websocket: WebSocket) -> None:
    await websocket.accept()
    enricher: AccessEventEnricher | None = getattr(websocket.app.state, "access_events", None)
    if enricher is None:
        await websocket.send_json({"type": "system_status", "status": "monitoring_unavailable"})
        await websocket.close(code=1013, reason="Monitoramento não configurado")
        return

    subscription = enricher.subscribe()
    try:
        while True:
            event_task = asyncio.create_task(subscription.get())
            receive_task = asyncio.create_task(websocket.receive())
            done, pending = await asyncio.wait(
                {event_task, receive_task}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            for task in pending:
                with suppress(asyncio.CancelledError):
                    await task
            if receive_task in done:
                message = receive_task.result()
                if message["type"] == "websocket.disconnect":
                    return
            if event_task in done:
                await websocket.send_json(_event_message(event_task.result()))
    except WebSocketDisconnect:
        return
    finally:
        enricher.unsubscribe(subscription)


def _event_message(enriched: EnrichedAccessEvent) -> dict:
    event = enriched.event
    return {
        "type": "access_event",
        "data": {
            "external_id": event.external_id,
            "device_id": event.device_id,
            "employee_no": event.employee_no,
            "access_type": event.access_type,
            "success": event.success,
            "event_time": event.event_time.isoformat(),
            "snapshot_url": _snapshot_url(event),
            "resident": _resident_message(enriched.resident),
            "device": _device_message(enriched.device),
        },
    }


def _device_message(device: DeviceSummary | None) -> dict | None:
    return None if device is None else {"id": device.id, "name": device.name}


def _snapshot_url(event: AccessEvent) -> str | None:
    """Point at the copy the backend kept; the device path is unreachable from a browser."""
    if event.snapshot is None:
        return None
    return f"/access-events/{event.device_id}/{quote(event.external_id)}/snapshot"


def _resident_message(resident: ResidentSummary | None) -> dict | None:
    if resident is None:
        return None
    return {
        "id": resident.id,
        "employee_no": resident.employee_no,
        "name": resident.name,
        "apartment": resident.apartment,
        "block": resident.block,
        "photo_url": f"/residents/{resident.employee_no}/photo" if resident.has_photo else None,
    }
