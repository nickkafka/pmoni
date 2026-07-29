from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.application.services.resident_sync import ResidentSyncService
from app.core.config import settings
from app.database.database import get_session
from app.domain.entities.resident import Resident
from app.hikvision.factory import HikvisionPersonDirectoryFactory
from app.infrastructure.persistence.device_repository import SqlAlchemyDeviceRepository
from app.infrastructure.persistence.resident_repository import SqlAlchemyResidentRepository
from app.infrastructure.security import CredentialProtectionUnavailable, FernetCredentialCipher
from app.schemas.resident import ResidentLocationUpdate, ResidentRead, ResidentSyncRead

router = APIRouter(prefix="/residents", tags=["residents"])


def get_repository(session: Session = Depends(get_session)) -> SqlAlchemyResidentRepository:
    return SqlAlchemyResidentRepository(session)


@router.get("", response_model=list[ResidentRead], dependencies=[Depends(require_admin)])
def list_residents(
    repository: SqlAlchemyResidentRepository = Depends(get_repository),
) -> list[Resident]:
    return repository.list_all()


# Sem sessão de propósito: a tela da portaria mostra esta foto e sobe sozinha.
@router.get("/{resident_id}/photo")
def read_resident_photo(
    resident_id: int, repository: SqlAlchemyResidentRepository = Depends(get_repository)
) -> Response:
    photo = repository.get_photo(resident_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto não sincronizada.")
    return Response(content=photo, media_type="image/jpeg")


@router.patch("/{resident_id}", response_model=ResidentRead, dependencies=[Depends(require_admin)])
def update_resident_location(
    resident_id: int,
    payload: ResidentLocationUpdate,
    repository: SqlAlchemyResidentRepository = Depends(get_repository),
) -> Resident:
    resident = repository.set_location(
        resident_id, apartment=payload.apartment, block=payload.block
    )
    if resident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Morador não encontrado.")
    return resident


@router.post("/sync/{device_id}", response_model=ResidentSyncRead, dependencies=[Depends(require_admin)])
async def sync_residents(
    device_id: int,
    refresh_photos: bool = False,
    session: Session = Depends(get_session),
    repository: SqlAlchemyResidentRepository = Depends(get_repository),
) -> ResidentSyncRead:
    devices = SqlAlchemyDeviceRepository(session)
    device = devices.get(device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispositivo não encontrado.")
    try:
        cipher = FernetCredentialCipher(settings.DEVICE_CREDENTIALS_KEY)
    except CredentialProtectionUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    service = ResidentSyncService(repository, HikvisionPersonDirectoryFactory(devices, cipher))
    report = await service.sync(device, refresh_photos=refresh_photos)
    return ResidentSyncRead.model_validate(report)
