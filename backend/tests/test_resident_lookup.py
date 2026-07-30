import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.database import Base
from app.domain.entities.resident import EnrolledPerson
from app.infrastructure.persistence.resident_lookup import SessionScopedResidentLookup
from app.infrastructure.persistence.resident_repository import SqlAlchemyResidentRepository

SEM_FOTO, COM_FOTO = None, b"jpeg"


class SessionScopedResidentLookupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.addCleanup(self.session.close)
        self.repository = SqlAlchemyResidentRepository(self.session)
        # A mesma sessão em todas as buscas: o teste não precisa de isolamento.
        self.lookup = SessionScopedResidentLookup(lambda: self.session)

    def enrol(self, device_id: int, employee_no: str, name: str, photo: bytes | None) -> int:
        self.repository.save_enrollment(
            device_id, EnrolledPerson(employee_no, name, f"/face/{device_id}.jpg"), photo=photo
        )
        return self.repository.find(device_id, employee_no).id

    def test_uses_the_picture_of_the_enrollment_that_passed(self) -> None:
        proprio = self.enrol(1, "2", "nk", COM_FOTO)
        self.enrol(2, "2", "nk", COM_FOTO)

        self.assertEqual(self.lookup.find(1, "2").photo_id, proprio)

    def test_borrows_the_picture_when_its_own_device_kept_none(self) -> None:
        com_foto = self.enrol(1, "2", "nk", COM_FOTO)
        self.enrol(2, "2", "nk", SEM_FOTO)

        self.assertEqual(self.lookup.find(2, "2").photo_id, com_foto)

    def test_never_borrows_from_someone_else_with_the_same_identifier(self) -> None:
        self.enrol(1, "2", "nk", COM_FOTO)
        self.enrol(2, "2", "naldo", SEM_FOTO)

        emprestado = self.lookup.find(2, "2")

        self.assertEqual(emprestado.name, "naldo")
        self.assertIsNone(emprestado.photo_id)

    def test_reports_no_picture_when_no_device_has_one(self) -> None:
        self.enrol(1, "2", "nk", SEM_FOTO)

        self.assertIsNone(self.lookup.find(1, "2").photo_id)

    def test_keeps_the_identity_of_the_enrollment_that_passed(self) -> None:
        self.enrol(1, "2", "nk", COM_FOTO)
        proprio = self.enrol(2, "2", "nk", SEM_FOTO)

        encontrado = self.lookup.find(2, "2")

        self.assertEqual(encontrado.id, proprio)

    def test_reports_nobody_for_an_identifier_that_device_never_had(self) -> None:
        self.enrol(1, "2", "nk", COM_FOTO)

        self.assertIsNone(self.lookup.find(9, "2"))
