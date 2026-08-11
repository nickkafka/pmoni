from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.application.services.resident_search import search
from app.application.services.resident_sync import ResidentSyncService
from app.core.config import settings
from app.database.database import get_session
from app.domain.entities.resident import Resident
from app.hikvision.factory import HikvisionPersonDirectoryFactory
from app.infrastructure.persistence.device_repository import SqlAlchemyDeviceRepository
from app.infrastructure.persistence.resident_repository import SqlAlchemyResidentRepository
from app.infrastructure.security import CredentialProtectionUnavailable, FernetCredentialCipher
from app.schemas.resident import (
    DirectoryPersonRead,
    PersonDetailsUpdate,
    ResidentLocationUpdate,
    ResidentPurgeRead,
    ResidentRead,
    ResidentSyncRead,
)

router = APIRouter(prefix="/residents", tags=["residents"])


def get_repository(session: Session = Depends(get_session)) -> SqlAlchemyResidentRepository:
    return SqlAlchemyResidentRepository(session)


@router.get("", response_model=list[ResidentRead], dependencies=[Depends(require_admin)])
def list_residents(
    repository: SqlAlchemyResidentRepository = Depends(get_repository),
) -> list[Resident]:
    return repository.list_all()


# Sem sessão, como a foto e o restante da portaria: a guarita sobe sozinha e não tem
# quem digite uma senha. O que protege este dado é a API só escutar em 127.0.0.1 —
# ela não existe na rede, apenas para a máquina da própria portaria.
@router.get("/search", response_model=list[DirectoryPersonRead])
def search_residents(
    q: str = Query(default="", max_length=128),
    session: Session = Depends(get_session),
    repository: SqlAlchemyResidentRepository = Depends(get_repository),
) -> list[DirectoryPersonRead]:
    """Find a resident by name, document or apartment when the face was not read."""
    people = search(repository.list_directory(), q)
    names = {device.id: device.name for device in SqlAlchemyDeviceRepository(session).list_enabled()}
    return [
        DirectoryPersonRead(
            employee_no=person.employee_no,
            name=person.name,
            apartment=person.apartment,
            block=person.block,
            document=person.document,
            photo_id=person.photo_id,
            device_ids=list(person.device_ids),
            # Um cadastro pode ter sobrado de um equipamento removido; a busca segue
            # valendo, apenas sem o nome dele.
            device_names=[names[i] for i in person.device_ids if i in names],
        )
        for person in people
    ]


# Sem sessão de propósito: a tela da portaria mostra esta foto e sobe sozinha.
@router.get("/{resident_id}/photo")
def read_resident_photo(
    resident_id: int, repository: SqlAlchemyResidentRepository = Depends(get_repository)
) -> Response:
    photo = repository.get_photo(resident_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foto não sincronizada.")
    return Response(content=photo, media_type="image/jpeg")


@router.patch("/person", response_model=list[ResidentRead], dependencies=[Depends(require_admin)])
def update_person_details(
    payload: PersonDetailsUpdate,
    repository: SqlAlchemyResidentRepository = Depends(get_repository),
) -> list[Resident]:
    """Record apartment, block and document for a person, on all their enrollments.

    This is where the Sigma import will deliver what it reads from
    `GET /v1/accounts/{accountId}/dwellers`: it knows people, not enrollments, and
    a person walks through several gates. Writing per person keeps the answer the
    same at every one of them.

    Only the fields actually present in the request are written, so an import that
    knows the apartment cannot blank a document — while a field sent as null is
    cleared on purpose, which is what the operator emptying a box means.
    """
    changes = payload.model_dump(exclude_unset=True, exclude={"employee_no", "name"})
    written = repository.set_person_details(payload.employee_no, payload.name, changes)
    if not written:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Morador não encontrado, ou nenhum campo informado.",
        )
    return written


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


@router.delete("", response_model=ResidentPurgeRead, dependencies=[Depends(require_admin)])
def purge_residents(
    repository: SqlAlchemyResidentRepository = Depends(get_repository),
) -> ResidentPurgeRead:
    """Empty the resident directory.

    Only the local copy is touched: the people remain enrolled on the equipment,
    and synchronising brings them back — the apartments typed here do not.
    """
    return ResidentPurgeRead(removed=repository.drop_all())


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
