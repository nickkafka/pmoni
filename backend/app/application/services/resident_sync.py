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
    removed: int
    without_photo: int
    """Pessoas cujo rosto o equipamento guarda só como template, sem imagem."""
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
        if device.id is None:
            raise ValueError("O dispositivo precisa estar persistido para sincronizar.")
        directory = self._directory_factory.create(device)
        created = updated = downloaded = failures = removed = without_photo = 0
        seen: set[str] = set()
        try:
            async for person in directory.list_enrolled():
                seen.add(person.employee_no)
                try:
                    photo, missing = await self._photo_for(
                        directory, device.id, person, refresh_photos=refresh_photos
                    )
                except Exception:
                    failures += 1
                    logger.exception("Falha ao obter a foto de {}.", person.employee_no)
                    photo = None
                else:
                    without_photo += 1 if missing else 0
                if photo is not None:
                    downloaded += 1
                if self._repository.save_enrollment(device.id, person, photo=photo):
                    created += 1
                else:
                    updated += 1
            # Only after reading the whole directory, and never on an empty answer:
            # a device that momentarily reports nobody must not erase its people.
            if seen:
                removed = self._repository.drop_missing(device.id, seen)
        finally:
            await directory.close()
        logger.info(
            "Sincronização do dispositivo {}: {} novos, {} atualizados, {} fotos, "
            "{} removidos, {} sem foto no equipamento, {} falhas.",
            device.id, created, updated, downloaded, removed, without_photo, failures,
        )
        return ResidentSyncReport(created, updated, downloaded, removed, without_photo, failures)

    async def _photo_for(
        self, directory, device_id: int, person: EnrolledPerson, *, refresh_photos: bool
    ) -> tuple[bytes | None, bool]:
        """Return the image to store, and whether the device has none for this person.

        Downloads only when the photo is missing here or its enrollment changed, so
        an unchanged one comes back as nothing to store and nothing missing.
        """
        if person.photo_reference is None:
            return None, True
        stored = self._repository.photo_reference_of(device_id, person.employee_no)
        if not refresh_photos and stored == person.photo_reference:
            return None, False
        image = await directory.fetch_photo(person.photo_reference)
        return image, image is None
