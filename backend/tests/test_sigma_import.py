import unittest
from datetime import datetime

from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.application.services.sigma_import import SigmaImportService, outcome_of
from app.database.database import Base
from app.domain.entities.automation import ImportStatus
from app.domain.entities.resident import EnrolledPerson
from app.domain.entities.sigma import SigmaDweller
from app.infrastructure.persistence.resident_repository import SqlAlchemyResidentRepository
from app.infrastructure.persistence.sigma_repository import SqlAlchemySigmaRepository
from app.infrastructure.security import FernetCredentialCipher
from app.sigma.client import SigmaClient


class FakeClient:
    """Stands in for Sigma, answering the dwellers a test cares about."""

    def __init__(self, pessoas: list[SigmaDweller]) -> None:
        self._pessoas = pessoas

    async def dwellers(self, account_id: int) -> list[SigmaDweller]:
        return self._pessoas


def dweller(enrollment: str, name: str, **campos) -> SigmaDweller:
    return SigmaDweller(
        enrollment=enrollment, name=name,
        apartment=campos.get("apartment"), block=campos.get("block"),
        cpf=campos.get("cpf"), rg=campos.get("rg"),
    )


class SigmaImportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        self.session = Session(engine)
        self.addCleanup(self.session.close)
        self.residents = SqlAlchemyResidentRepository(self.session)

    def enrol(self, device_id: int, employee_no: str, name: str) -> None:
        self.residents.save_enrollment(
            device_id, EnrolledPerson(employee_no, name, None), photo=None
        )

    async def run_import(self, pessoas: list[SigmaDweller]):
        return await SigmaImportService(self.residents).run(FakeClient(pessoas), 1)

    async def test_fills_apartment_block_and_both_documents(self) -> None:
        self.enrol(1, "59", "Nicholas Kafka de Matos")

        report = await self.run_import([
            dweller("59", "Nicholas Kafka de Matos", apartment="1", block="TI",
                    cpf="44218291888", rg="530072889")
        ])

        self.assertEqual((report.read, report.updated, report.unmatched), (1, 1, []))
        gravado = self.residents.find(1, "59")
        self.assertEqual(gravado.apartment, "1")
        self.assertEqual(gravado.block, "TI")
        self.assertEqual(gravado.cpf, "44218291888")
        self.assertEqual(gravado.rg, "530072889")

    async def test_writes_to_every_enrollment_of_the_person(self) -> None:
        """A pessoa passa em sete portarias e precisa responder igual em todas."""
        for device_id in range(1, 8):
            self.enrol(device_id, "59", "Nicholas Kafka de Matos")

        await self.run_import([dweller("59", "Nicholas Kafka de Matos", apartment="1")])

        for device_id in range(1, 8):
            self.assertEqual(self.residents.find(device_id, "59").apartment, "1")

    async def test_refuses_to_write_when_the_name_differs(self) -> None:
        """Casar só pelo ID poria o endereço de um no cadastro de outro (ADR 0010)."""
        self.enrol(1, "2", "nk")

        report = await self.run_import([dweller("2", "Outra Pessoa", apartment="301")])

        self.assertEqual(report.updated, 0)
        self.assertIn("Outra Pessoa", report.unmatched[0])
        self.assertIsNone(self.residents.find(1, "2").apartment)

    async def test_reports_who_is_not_on_any_facial(self) -> None:
        report = await self.run_import([dweller("99", "Fantasma", apartment="1")])

        self.assertEqual(report.updated, 0)
        self.assertEqual(len(report.unmatched), 1)

    async def test_never_blanks_what_sigma_left_empty(self) -> None:
        """Um cadastro incompleto no Sigma não pode apagar o que foi digitado à mão."""
        self.enrol(1, "59", "Nicholas")
        self.residents.set_person_details("59", "Nicholas", {"cpf": "digitado-a-mao"})

        await self.run_import([dweller("59", "Nicholas", apartment="1", cpf=None)])

        gravado = self.residents.find(1, "59")
        self.assertEqual(gravado.apartment, "1")
        self.assertEqual(gravado.cpf, "digitado-a-mao")

    async def test_skips_somebody_sigma_knows_nothing_useful_about(self) -> None:
        self.enrol(1, "59", "Nicholas")

        report = await self.run_import([dweller("59", "Nicholas")])

        self.assertEqual(report.updated, 0)
        self.assertEqual(report.unmatched, [])

    async def test_matches_through_the_accents_sigma_writes(self) -> None:
        """O Sigma escreve "Andre Lourenço"; a facial guardou "Andre Lourenco"."""
        self.enrol(1, "22", "Andre Lourenco")

        report = await self.run_import([dweller("22", "Andre Lourenço", apartment="0")])

        self.assertEqual(report.updated, 1)
        self.assertEqual(self.residents.find(1, "22").apartment, "0")

    async def test_matches_a_name_the_device_truncated(self) -> None:
        """A facial corta em 32 caracteres: o Nascimento vira "do Nas"."""
        self.enrol(1, "164", "Peterson Henrique Freitas do Nas")

        report = await self.run_import([
            dweller("164", "Peterson Henrique Freitas do Nascimento", apartment="1")
        ])

        self.assertEqual(report.updated, 1)
        self.assertEqual(self.residents.find(1, "164").apartment, "1")

    async def test_a_short_name_never_swallows_a_longer_one(self) -> None:
        """Sem o limite de truncamento, "Ana" casaria com "Ana Maria" — outra pessoa."""
        self.enrol(1, "5", "Ana")

        report = await self.run_import([dweller("5", "Ana Maria", apartment="301")])

        self.assertEqual(report.updated, 0)
        self.assertIsNone(self.residents.find(1, "5").apartment)

    async def test_refuses_when_the_same_identifier_folds_to_two_names(self) -> None:
        """Duas faciais grafaram o mesmo ID diferente; qual das duas é a pessoa?

        Ignorar acento resolve a grafia, mas não decide entre dois cadastros que
        viram o mesmo nome depois de ignorá-lo. Na dúvida, não gravar.
        """
        self.enrol(1, "22", "Andre Lourenço")
        self.enrol(2, "22", "Andre Lourenco")

        report = await self.run_import([dweller("22", "André Lourenço", apartment="9")])

        self.assertEqual(report.updated, 0)
        self.assertEqual(len(report.unmatched), 1)
        self.assertIsNone(self.residents.find(1, "22").apartment)

    async def test_one_person_missing_does_not_stop_the_others(self) -> None:
        self.enrol(1, "59", "Nicholas")

        report = await self.run_import([
            dweller("59", "Nicholas", apartment="1"),
            dweller("77", "Ausente", apartment="2"),
        ])

        self.assertEqual(report.updated, 1)
        self.assertEqual(len(report.unmatched), 1)


class OutcomeTests(unittest.TestCase):
    def test_all_matched_is_success(self) -> None:
        from app.domain.entities.sigma import SigmaImportReport

        status, mensagem = outcome_of(SigmaImportReport(read=10, updated=10, unmatched=[]))

        self.assertEqual(status, ImportStatus.OK)
        self.assertIn("10 de 10", mensagem)

    def test_some_missing_is_partial(self) -> None:
        from app.domain.entities.sigma import SigmaImportReport

        status, mensagem = outcome_of(
            SigmaImportReport(read=10, updated=8, unmatched=["A (ID 1)", "B (ID 2)"])
        )

        self.assertEqual(status, ImportStatus.PARTIAL)
        self.assertIn("A (ID 1)", mensagem)

    def test_nothing_matching_is_a_failure(self) -> None:
        """Nada casar quase sempre é a conta errada, não um cadastro todo divergente."""
        from app.domain.entities.sigma import SigmaImportReport

        status, _ = outcome_of(SigmaImportReport(read=10, updated=0, unmatched=["A"] * 10))

        self.assertEqual(status, ImportStatus.FAILED)


class SigmaTokenTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        self.session = Session(engine)
        self.addCleanup(self.session.close)
        self.repository = SqlAlchemySigmaRepository(self.session)
        self.cipher = FernetCredentialCipher(Fernet.generate_key().decode())

    def test_starts_unconfigured(self) -> None:
        self.assertFalse(self.repository.get().configured)

    def test_the_token_is_stored_encrypted(self) -> None:
        """Em claro no banco, qualquer cópia do arquivo levaria o token junto."""
        self.repository.save(encrypted_token=self.cipher.encrypt("segredo"), account_id=1)

        guardado = self.repository.encrypted_token()
        self.assertNotIn("segredo", guardado)
        self.assertEqual(self.cipher.decrypt(guardado), "segredo")

    def test_what_the_interface_sees_never_carries_the_token(self) -> None:
        self.repository.save(encrypted_token=self.cipher.encrypt("segredo"), account_id=583775)

        visto = self.repository.get()

        self.assertTrue(visto.configured)
        self.assertNotIn("token", {campo for campo in visto.__slots__})

    def test_saving_without_a_token_keeps_the_stored_one(self) -> None:
        """A tela não lê o token, então não teria como reenviá-lo ao corrigir a conta."""
        self.repository.save(encrypted_token=self.cipher.encrypt("segredo"), account_id=1)

        self.repository.save(encrypted_token=None, account_id=999)

        self.assertEqual(self.cipher.decrypt(self.repository.encrypted_token()), "segredo")
        self.assertEqual(self.repository.get().account_id, 999)

    def test_forgetting_the_token_leaves_it_unconfigured(self) -> None:
        self.repository.save(encrypted_token=self.cipher.encrypt("segredo"), account_id=1)

        self.repository.forget_token()

        self.assertFalse(self.repository.get().configured)
        self.assertIsNone(self.repository.encrypted_token())

    def test_records_how_an_import_went(self) -> None:
        self.repository.record_import(
            finished_at=datetime(2026, 8, 14, 10, 0), status=ImportStatus.OK, message="tudo certo"
        )

        visto = self.repository.get()
        self.assertEqual(visto.last_status, ImportStatus.OK)
        self.assertEqual(visto.last_message, "tudo certo")


class SigmaClientMappingTests(unittest.TestCase):
    """O mapeamento medido contra a API real em 2026-08-14."""

    def test_reads_the_fields_pmoni_needs(self) -> None:
        pessoa = SigmaClient._to_dweller({
            "id": 926021,
            "commonEnroll": 59,
            "name": "Nicholas Kafka de Matos",
            "federalRegister": "44218291888",
            "nationalId": "530072889",
            "unities": [{"block": "TI", "blockId": 8022, "unit": "1", "unitId": 80296}],
        })

        self.assertEqual(pessoa.enrollment, "59")
        self.assertEqual(pessoa.cpf, "44218291888")
        self.assertEqual(pessoa.rg, "530072889")
        self.assertEqual(pessoa.apartment, "1")
        self.assertEqual(pessoa.block, "TI")

    def test_uses_common_enroll_and_not_the_sigma_id(self) -> None:
        """O employeeNo das faciais é o commonEnroll: bateu em 49 de 49, o id em nenhum."""
        pessoa = SigmaClient._to_dweller({"id": 926021, "commonEnroll": 59, "name": "x"})

        self.assertEqual(pessoa.enrollment, "59")

    def test_an_empty_field_means_unknown_and_not_blank(self) -> None:
        pessoa = SigmaClient._to_dweller(
            {"commonEnroll": 1, "name": "x", "federalRegister": "  ", "unities": []}
        )

        self.assertIsNone(pessoa.cpf)
        self.assertIsNone(pessoa.apartment)


if __name__ == "__main__":
    unittest.main()
