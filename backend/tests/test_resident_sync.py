import unittest
from collections.abc import AsyncIterator

from app.application.ports.person_directory import PersonDirectory
from app.application.ports.person_directory_factory import PersonDirectoryFactory
from app.application.ports.resident_repository import ResidentRepository
from app.application.services.resident_sync import ResidentSyncService
from app.domain.entities.device import Device
from app.domain.entities.resident import EnrolledPerson, Resident

DEVICE = Device(1, "Portaria", "192.168.1.10", 80, "admin", "DS-K1T342MFWX", True)


class FakeDirectory(PersonDirectory):
    def __init__(self, people: list[EnrolledPerson], *, broken: set[str] | None = None) -> None:
        self.people = people
        self.broken = broken or set()
        self.downloaded: list[str] = []
        self.closed = False

    async def list_enrolled(self) -> AsyncIterator[EnrolledPerson]:
        for person in self.people:
            yield person

    async def fetch_photo(self, reference: str) -> bytes | None:
        if reference in self.broken:
            raise ConnectionError("foto indisponível")
        self.downloaded.append(reference)
        return b"jpeg-" + reference.encode()

    async def close(self) -> None:
        self.closed = True


class FakeFactory(PersonDirectoryFactory):
    def __init__(self, directory: FakeDirectory) -> None:
        self.directory = directory

    def create(self, device: Device) -> PersonDirectory:
        return self.directory


class FakeRepository(ResidentRepository):
    def __init__(self) -> None:
        self.rows: dict[tuple[int, str], dict] = {}

    def list_all(self) -> list[Resident]:
        raise NotImplementedError

    def find(self, device_id: int, employee_no: str) -> Resident | None:
        raise NotImplementedError

    def get_photo(self, resident_id: int) -> bytes | None:
        raise NotImplementedError

    def photo_of(self, device_id: int, employee_no: str) -> bytes | None:
        return self.rows.get((device_id, employee_no), {}).get("photo")

    def photo_reference_of(self, device_id: int, employee_no: str) -> str | None:
        row = self.rows.get((device_id, employee_no))
        return row.get("photo_reference") if row and row.get("photo") else None

    def save_enrollment(self, device_id, person, *, photo) -> bool:
        key = (device_id, person.employee_no)
        created = key not in self.rows
        row = self.rows.setdefault(key, {})
        row["name"] = person.name
        if photo is not None:
            row["photo"], row["photo_reference"] = photo, person.photo_reference
        return created

    def set_location(self, resident_id, *, apartment, block):
        raise NotImplementedError


def person(employee_no: str, name: str, reference: str | None = None) -> EnrolledPerson:
    return EnrolledPerson(employee_no, name, reference)


class ResidentSyncServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_stores_people_and_photos_on_first_sync(self) -> None:
        directory = FakeDirectory([person("2", "nk", "/face/2.jpg"), person("195", "Janaina", "/face/195.jpg")])
        repository = FakeRepository()

        report = await ResidentSyncService(repository, FakeFactory(directory)).sync(DEVICE)

        self.assertEqual((report.created, report.updated, report.photos_downloaded), (2, 0, 2))
        self.assertEqual(repository.photo_of(1, "2"), b"jpeg-/face/2.jpg")
        self.assertTrue(directory.closed)

    async def test_skips_downloading_an_unchanged_photo(self) -> None:
        directory = FakeDirectory([person("2", "nk", "/face/2.jpg")])
        repository = FakeRepository()
        service = ResidentSyncService(repository, FakeFactory(directory))
        await service.sync(DEVICE)

        report = await service.sync(DEVICE)

        self.assertEqual(report.photos_downloaded, 0)
        self.assertEqual(directory.downloaded, ["/face/2.jpg"])
        self.assertEqual(report.updated, 1)

    async def test_downloads_again_when_the_enrollment_changed(self) -> None:
        directory = FakeDirectory([person("2", "nk", "/face/2.jpg")])
        repository = FakeRepository()
        service = ResidentSyncService(repository, FakeFactory(directory))
        await service.sync(DEVICE)

        directory.people = [person("2", "nk", "/face/9.jpg")]
        report = await service.sync(DEVICE)

        self.assertEqual(report.photos_downloaded, 1)
        self.assertEqual(repository.photo_of(1, "2"), b"jpeg-/face/9.jpg")

    async def test_refresh_forces_a_new_download(self) -> None:
        directory = FakeDirectory([person("2", "nk", "/face/2.jpg")])
        service = ResidentSyncService(FakeRepository(), FakeFactory(directory))
        await service.sync(DEVICE)

        report = await service.sync(DEVICE, refresh_photos=True)

        self.assertEqual(report.photos_downloaded, 1)

    async def test_keeps_the_person_when_the_photo_fails(self) -> None:
        directory = FakeDirectory(
            [person("2", "nk", "/face/2.jpg")], broken={"/face/2.jpg"}
        )
        repository = FakeRepository()

        report = await ResidentSyncService(repository, FakeFactory(directory)).sync(DEVICE)

        self.assertEqual((report.created, report.failures), (1, 1))
        self.assertEqual(repository.rows[(1, "2")]["name"], "nk")
        self.assertIsNone(repository.photo_of(1, "2"))

    async def test_stores_a_person_without_any_enrolled_face(self) -> None:
        repository = FakeRepository()
        directory = FakeDirectory([person("2", "nk", None)])

        report = await ResidentSyncService(repository, FakeFactory(directory)).sync(DEVICE)

        self.assertEqual((report.created, report.photos_downloaded), (1, 0))
        self.assertEqual(directory.downloaded, [])

    async def test_keeps_apart_two_devices_that_gave_the_same_identifier(self) -> None:
        """Devices enrolled separately reuse numbers for different people."""
        repository = FakeRepository()
        portaria = FakeDirectory([person("2", "nk", "/face/nk.jpg")])
        entrada = Device(9, "Entrada", "192.168.1.20", 80, "admin", None, True)
        outra = FakeDirectory([person("2", "naldo", "/face/naldo.jpg")])

        await ResidentSyncService(repository, FakeFactory(portaria)).sync(DEVICE)
        await ResidentSyncService(repository, FakeFactory(outra)).sync(entrada)

        self.assertEqual(repository.rows[(1, "2")]["name"], "nk")
        self.assertEqual(repository.rows[(9, "2")]["name"], "naldo")
        self.assertEqual(repository.photo_of(1, "2"), b"jpeg-/face/nk.jpg")
        self.assertEqual(repository.photo_of(9, "2"), b"jpeg-/face/naldo.jpg")

    async def test_closes_the_directory_when_the_sync_fails(self) -> None:
        directory = FakeDirectory([])

        async def explode() -> AsyncIterator[EnrolledPerson]:
            raise ConnectionError("equipamento offline")
            yield  # pragma: no cover

        directory.list_enrolled = explode
        service = ResidentSyncService(FakeRepository(), FakeFactory(directory))

        with self.assertRaises(ConnectionError):
            await service.sync(DEVICE)

        self.assertTrue(directory.closed)
