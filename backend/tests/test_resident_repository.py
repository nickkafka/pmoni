import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.database import Base
from app.domain.entities.resident import EnrolledPerson
from app.infrastructure.persistence.models import DeviceRecord
from app.infrastructure.persistence.resident_repository import SqlAlchemyResidentRepository


def person(employee_no: str, name: str) -> EnrolledPerson:
    return EnrolledPerson(employee_no, name, f"/face/{employee_no}.jpg")


class SqlAlchemyResidentRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        self.session = Session(engine)
        self.addCleanup(self.session.close)
        self.repository = SqlAlchemyResidentRepository(self.session)

    def enrol(self, device_id: int, employee_no: str, name: str) -> None:
        self.repository.save_enrollment(device_id, person(employee_no, name), photo=b"jpeg")

    def enrol_without_photo(self, device_id: int, employee_no: str, name: str) -> None:
        self.repository.save_enrollment(device_id, person(employee_no, name), photo=None)

    def test_lends_the_picture_from_another_device(self) -> None:
        """Faciais que gravam só o template deixam o cadastro sem imagem."""
        self.enrol(1, "2", "nk")
        self.enrol_without_photo(2, "2", "nk")

        holder = self.repository.find_photo_holder("2", "nk")

        self.assertEqual(holder, self.repository.find(1, "2").id)

    def test_refuses_to_lend_across_people_that_share_an_identifier(self) -> None:
        """O ID sozinho nomeia pessoas diferentes em faciais cadastradas à parte."""
        self.enrol(1, "2", "nk")
        self.enrol_without_photo(2, "2", "naldo")

        self.assertIsNone(self.repository.find_photo_holder("2", "naldo"))

    def test_writes_person_details_to_every_enrollment_that_names_them(self) -> None:
        """O apartamento é da pessoa: ela responde igual em qualquer portaria."""
        self.enrol(1, "7", "nk")
        self.enrol(2, "7", "nk")

        written = self.repository.set_person_details(
            "7", "nk", {"apartment": "301", "cpf": "123.456.789-00"}
        )

        self.assertEqual(len(written), 2)
        for device_id in (1, 2):
            resident = self.repository.find(device_id, "7")
            self.assertEqual(resident.apartment, "301")
            self.assertEqual(resident.cpf, "123.456.789-00")

    def test_never_spills_details_onto_someone_sharing_an_identifier(self) -> None:
        """Gravar só pelo ID poria o endereço de um no cadastro do outro (ADR 0010)."""
        self.enrol(1, "2", "nk")
        self.enrol(2, "2", "naldo")

        self.repository.set_person_details("2", "nk", {"apartment": "301"})

        self.assertEqual(self.repository.find(1, "2").apartment, "301")
        self.assertIsNone(self.repository.find(2, "2").apartment)

    def test_leaves_alone_the_fields_an_import_does_not_know(self) -> None:
        """Uma importação que só traz o apartamento não pode apagar o documento."""
        self.enrol(1, "7", "nk")
        self.repository.set_person_details("7", "nk", {"cpf": "123.456.789-00"})

        self.repository.set_person_details("7", "nk", {"apartment": "301"})

        resident = self.repository.find(1, "7")
        self.assertEqual(resident.apartment, "301")
        self.assertEqual(resident.cpf, "123.456.789-00")

    def test_clears_a_field_sent_as_none(self) -> None:
        """Ausente e vazio são coisas diferentes: quem esvaziou a caixa quis esvaziar."""
        self.enrol(1, "7", "nk")
        self.repository.set_person_details("7", "nk", {"apartment": "301"})

        self.repository.set_person_details("7", "nk", {"apartment": None})

        self.assertIsNone(self.repository.find(1, "7").apartment)

    def test_refuses_a_field_that_is_not_the_persons(self) -> None:
        """Nome e foto pertencem ao equipamento; deixar passar aqui os sobrescreveria."""
        self.enrol(1, "7", "nk")

        with self.assertRaises(ValueError):
            self.repository.set_person_details("7", "nk", {"name": "outro"})

    def test_reports_nobody_written_for_an_unknown_person(self) -> None:
        self.assertEqual(self.repository.set_person_details("7", "ninguem", {"apartment": "301"}), [])

    def test_reads_the_directory_without_the_photos(self) -> None:
        """A busca lê o cadastro inteiro a cada tecla; as imagens não podem vir junto."""
        self.enrol(1, "7", "nk")
        self.enrol_without_photo(2, "8", "naldo")

        directory = {resident.employee_no: resident for resident in self.repository.list_directory()}

        self.assertTrue(directory["7"].has_photo)
        self.assertFalse(directory["8"].has_photo)

    def test_reports_no_holder_when_nobody_has_a_picture(self) -> None:
        self.enrol_without_photo(1, "2", "nk")

        self.assertIsNone(self.repository.find_photo_holder("2", "nk"))

    def test_always_lends_the_same_enrollment(self) -> None:
        self.enrol(1, "2", "nk")
        self.enrol(2, "2", "nk")

        primeiro = self.repository.find_photo_holder("2", "nk")

        self.assertEqual(self.repository.find_photo_holder("2", "nk"), primeiro)

    def test_empties_the_directory(self) -> None:
        self.enrol(1, "2", "nk")
        self.enrol(2, "2", "nk")

        removed = self.repository.drop_all()

        self.assertEqual(removed, 2)
        self.assertEqual(self.repository.list_all(), [])

    def test_reports_nothing_removed_from_an_empty_directory(self) -> None:
        self.assertEqual(self.repository.drop_all(), 0)

    def test_keeps_the_registered_equipment(self) -> None:
        """Clearing the people must not stop the monitoring."""
        self.session.add(
            DeviceRecord(
                name="Portaria", host="192.168.1.10", port=80, username="admin",
                credentials_encrypted="cifrado", enabled=True,
            )
        )
        self.session.commit()
        self.enrol(1, "2", "nk")

        self.repository.drop_all()

        self.assertEqual(self.session.query(DeviceRecord).count(), 1)

    def test_a_synchronisation_after_clearing_starts_over(self) -> None:
        self.enrol(1, "2", "nk")
        self.repository.drop_all()

        created = self.repository.save_enrollment(1, person("2", "nk"), photo=b"jpeg")

        self.assertTrue(created)
        self.assertEqual(len(self.repository.list_all()), 1)
