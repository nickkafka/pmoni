from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.application.services.device_manager import DeviceManager
from app.application.services.device_service import DeviceService
from app.core.config import settings
from app.database.database import get_session
from app.domain.entities.device import Device
from app.infrastructure.persistence.device_repository import SqlAlchemyDeviceRepository
from app.infrastructure.security import CredentialProtectionUnavailable, FernetCredentialCipher
from app.schemas.device import DeviceCreate, DeviceRead, DeviceUpdate

router = APIRouter(prefix="/devices", tags=["devices"])


def get_repository(session: Session = Depends(get_session)) -> SqlAlchemyDeviceRepository:
    return SqlAlchemyDeviceRepository(session)


def get_device_service(
    repository: SqlAlchemyDeviceRepository = Depends(get_repository),
) -> DeviceService:
    return DeviceService(
        repository=repository,
        credential_cipher=FernetCredentialCipher(settings.DEVICE_CREDENTIALS_KEY),
    )


def _encrypt(password: str) -> str:
    try:
        return FernetCredentialCipher(settings.DEVICE_CREDENTIALS_KEY).encrypt(password)
    except CredentialProtectionUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


async def _resupervise(request: Request, *, restart: tuple[int, ...] = ()) -> None:
    """Let the running supervisors adopt the change without restarting the API."""
    manager: DeviceManager | None = getattr(request.app.state, "device_manager", None)
    if manager is not None:
        await manager.refresh(restart=restart)


@router.get("", response_model=list[DeviceRead])
def list_devices(repository: SqlAlchemyDeviceRepository = Depends(get_repository)) -> list[Device]:
    return repository.list_enabled()


@router.post("", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
async def create_device(
    payload: DeviceCreate, request: Request, service: DeviceService = Depends(get_device_service)
) -> Device:
    device = Device(
        id=None, name=payload.name, host=payload.host, port=payload.port,
        username=payload.username, model=payload.model, enabled=True,
    )
    try:
        created = service.register(device, payload.password)
    except CredentialProtectionUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    await _resupervise(request)
    return created


@router.patch("/{device_id}", response_model=DeviceRead)
async def update_device(
    device_id: int,
    payload: DeviceUpdate,
    request: Request,
    repository: SqlAlchemyDeviceRepository = Depends(get_repository),
) -> Device:
    device = Device(
        id=device_id, name=payload.name, host=payload.host, port=payload.port,
        username=payload.username, model=payload.model, enabled=payload.enabled,
    )
    updated = repository.update(device, _encrypt(payload.password) if payload.password else None)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispositivo não encontrado.")
    await _resupervise(request, restart=(device_id,))
    return updated


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: int,
    request: Request,
    repository: SqlAlchemyDeviceRepository = Depends(get_repository),
) -> Response:
    if not repository.remove(device_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispositivo não encontrado.")
    await _resupervise(request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
