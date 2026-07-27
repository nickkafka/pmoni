from dataclasses import dataclass

from app.application.ports.person_directory_factory import PersonDirectoryFactory
from app.application.ports.resident_repository import ResidentRepository
from app.core.logger import logger
from app.domain.entities.device import Device
from app.domain.entities.resident import EnrolledPerson


@dataclass(frozen=True, slots=True)
class ResidentSyncReport:
    created: int
    updated: int
    photos_downloaded: int
    failures: int


class ResidentSyncService:
    """Copies the people enrolled on a device into the local resident directory.

    The device owns the identifier, the name and the photo; the apartment stays
    untouched because it is maintained in Monikraft until Sigma provides it.
    """

    def __init__(
        self, repository: ResidentRepository, directory_factory: PersonDirectoryFactory
    ) -> None:
        self._repository = repository
        self._directory_factory = directory_factory

    async def sync(self, device: Device, *, refresh_photos: bool = False) -> ResidentSyncReport:
        directory = self._directory_factory.create(device)
        created = updated = downloaded = failures = 0
        try:
            async for person in directory.list_enrolled():
                try:
                    photo = await self._photo_for(directory, person, refresh_photos=refresh_photos)
                except Exception:
                    failures += 1
                    logger.exception("Falha ao obter a foto de {}.", person.employee_no)
                    photo = None
                if photo is not None:
                    downloaded += 1
                if self._repository.save_enrollment(person, photo=photo, device_id=device.id):
                    created += 1
                else:
                    updated += 1
        finally:
            await directory.close()
        logger.info(
            "Sincronização do dispositivo {}: {} novos, {} atualizados, {} fotos, {} falhas.",
            device.id, created, updated, downloaded, failures,
        )
        return ResidentSyncReport(created, updated, downloaded, failures)

    async def _photo_for(self, directory, person: EnrolledPerson, *, refresh_photos: bool) -> bytes | None:
        """Download the photo only when it is missing or its enrollment changed."""
        if person.photo_reference is None:
            return None
        if not refresh_photos and self._repository.photo_reference_of(person.employee_no) == person.photo_reference:
            return None
        return await directory.fetch_photo(person.photo_reference)
