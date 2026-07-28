from fastapi import APIRouter, HTTPException, Request, Response, status

from app.application.ports.snapshot_store import SnapshotStore

router = APIRouter(prefix="/access-events", tags=["access-events"])


@router.get("/{device_id}/{external_id}/snapshot")
def read_snapshot(device_id: int, external_id: str, request: Request) -> Response:
    """Serve the capture the device took, which only the backend can reach."""
    store: SnapshotStore | None = getattr(request.app.state, "snapshots", None)
    image = store.get(device_id, external_id) if store else None
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Captura indisponível.")
    return Response(content=image, media_type="image/jpeg")
