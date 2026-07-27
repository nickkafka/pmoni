from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.application.services.device_service import DeviceService
from app.core.config import settings
from app.database.database import get_session
from app.domain.entities.device import Device
from app.infrastructure.persistence.device_repository import SqlAlchemyDeviceRepository
from app.infrastructure.security import CredentialProtectionUnavailable, FernetCredentialCipher
from app.schemas.device import DeviceCreate, DeviceRead

router = APIRouter(prefix="/devices", tags=["devices"])


def get_device_service(session: Session = Depends(get_session)) -> DeviceService:
    return DeviceService(
        repository=SqlAlchemyDeviceRepository(session),
        credential_cipher=FernetCredentialCipher(settings.DEVICE_CREDENTIALS_KEY),
    )


@router.get("", response_model=list[DeviceRead])
def list_devices(session: Session = Depends(get_session)) -> list[Device]:
    return SqlAlchemyDeviceRepository(session).list_enabled()


@router.post("", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
def create_device(payload: DeviceCreate, service: DeviceService = Depends(get_device_service)) -> Device:
    device = Device(
        id=None,
        name=payload.name,
        host=str(payload.host),
        port=payload.port,
        username=payload.username,
        model=payload.model,
        enabled=True,
    )
    try:
        return service.register(device, payload.password)
    except CredentialProtectionUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
