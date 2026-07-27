import asyncio
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.application.services.device_manager import DeviceManager
from app.domain.entities.access_event import AccessEvent

router = APIRouter()


@router.websocket("/ws/access-events")
async def access_events(websocket: WebSocket) -> None:
    await websocket.accept()
    manager: DeviceManager | None = getattr(websocket.app.state, "device_manager", None)
    if manager is None:
        await websocket.send_json({"type": "system_status", "status": "monitoring_unavailable"})
        await websocket.close(code=1013, reason="Monitoramento não configurado")
        return

    subscription = manager.subscribe()
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
        manager.unsubscribe(subscription)


def _event_message(event: AccessEvent) -> dict:
    return {
        "type": "access_event",
        "data": {
            "external_id": event.external_id,
            "device_id": event.device_id,
            "employee_no": event.employee_no,
            "access_type": event.access_type,
            "success": event.success,
            "event_time": event.event_time.isoformat(),
            "snapshot": event.snapshot,
        },
    }
