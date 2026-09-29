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
from app.sigma.client import SigmaClient, SigmaUnavailable


class FakeClient:
    """Stands in for Sigma, answering the dwellers a test cares about."""

    def __init__(
        self, pessoas: list[SigmaDweller], photos: dict[int, bytes] | None = None,
        *, photo_error: set[int] | None = None, visitantes: list[SigmaDweller] | None = None,
    ) -> None:
        self._pessoas = pessoas
        self._visitantes = visitantes or []
        self._photos = photos or {}
        self._photo_error = photo_error or set()
        self.photo_requests: list[int] = []

    async def dwellers(self, account_id: int) -> list[SigmaDweller]:
        return self._pessoas

    async def visitors(self, account_id: int) -> list[SigmaDweller]:
        return self._visitantes

    async def profile_photo(self, account_id: int, dweller_id: int) -> bytes | None:
        self.photo_requests.append(dweller_id)
        if dweller_id in self._photo_error:
            raise SigmaUnavailable("S3 fora do ar")
        return self._photos.get(dweller_id)


def dweller(enrollment: str, name: str, **campos) -> SigmaDweller:
    return SigmaDweller(
        enrollment=enrollment, name=name,
        apartment=campos.get("apartment"), block=campos.get("block"),
        cpf=campos.get("cpf"), rg=campos.get("rg"),
        sigma_id=campos.get("sigma_id"), enabled=campos.get("enabled", True),
        visitor=campos.get("visitor", False),
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


class SigmaPhotoTests(unittest.IsolatedAsyncioTestCase):
    """Visitantes e desativados: a facial guarda só o template, o Sigma guarda o rosto."""

    def setUp(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        self.session = Session(engine)
        self.addCleanup(self.session.close)
        self.residents = SqlAlchemyResidentRepository(self.session)

    def enrol(self, device_id: int, employee_no: str, name: str, *, photo: bytes | None = None) -> None:
        reference = f"/face/{employee_no}.jpg" if photo else None
        self.residents.save_enrollment(
            device_id, EnrolledPerson(employee_no, name, reference), photo=photo
        )

    async def test_brings_the_profile_photo_to_every_enrollment_without_one(self) -> None:
        for device_id in (1, 2):
            self.enrol(device_id, "170", "Visitante Silva")
        client = FakeClient([dweller("170", "Visitante Silva", sigma_id=900)], {900: b"\xff\xd8\xffjpeg"})

        report = await SigmaImportService(self.residents).run(client, 1)

        self.assertEqual(report.photos, 1)
        for device_id in (1, 2):
            self.assertTrue(self.residents.find(device_id, "170").has_photo)
        self.assertEqual(self.residents.photo_reference_of(1, "170"), "sigma:900")

    async def test_never_asks_for_a_photo_somebody_already_has_from_a_facial(self) -> None:
        """A foto da facial é a que o porteiro reconhece; a do Sigma só cobre a falta."""
        self.enrol(1, "170", "Adna", photo=b"da-facial")
        self.enrol(2, "170", "Adna")
        client = FakeClient([dweller("170", "Adna", sigma_id=900)], {900: b"do-sigma"})

        report = await SigmaImportService(self.residents).run(client, 1)

        self.assertEqual((report.photos, client.photo_requests), (0, []))
        self.assertIsNone(self.residents.photo_reference_of(2, "170"))

    async def test_a_disabled_person_still_on_a_facial_gets_photo_and_apartment(self) -> None:
        self.enrol(1, "88", "Ex Morador")
        client = FakeClient(
            [dweller("88", "Ex Morador", apartment="12", sigma_id=5, enabled=False)],
            {5: b"\x89PNGfoto"},
        )

        report = await SigmaImportService(self.residents).run(client, 1)

        gravado = self.residents.find(1, "88")
        self.assertEqual((gravado.apartment, gravado.has_photo), ("12", True))
        self.assertEqual((report.updated, report.photos), (1, 1))

    async def test_a_disabled_person_off_the_facials_is_not_reported_as_missing(self) -> None:
        """Quem saiu e já foi removido dos equipamentos é o esperado, não uma falha."""
        report = await SigmaImportService(self.residents).run(
            FakeClient([dweller("88", "Ex Morador", apartment="12", enabled=False)]), 1
        )

        self.assertEqual(report.unmatched, [])

    async def test_a_photo_that_fails_does_not_cost_the_rest_of_the_import(self) -> None:
        self.enrol(1, "1", "Ana Paula")
        self.enrol(1, "2", "Bruno Lima")
        client = FakeClient(
            [dweller("1", "Ana Paula", apartment="1", sigma_id=10),
             dweller("2", "Bruno Lima", apartment="2", sigma_id=20)],
            {20: b"\xff\xd8\xffok"},
            photo_error={10},
        )

        report = await SigmaImportService(self.residents).run(client, 1)

        self.assertEqual((report.updated, report.photos), (2, 1))
        self.assertTrue(self.residents.find(1, "2").has_photo)
        self.assertEqual(self.residents.find(1, "1").apartment, "1")

    async def test_a_face_the_facial_gains_later_replaces_the_sigma_photo(self) -> None:
        from app.application.services.resident_sync import ResidentSyncService
        from app.domain.entities.device import Device

        self.enrol(1, "170", "Visitante Silva")
        await SigmaImportService(self.residents).run(
            FakeClient([dweller("170", "Visitante Silva", sigma_id=900)], {900: b"do-sigma"}), 1
        )

        class Directory:
            async def list_enrolled(self):
                yield EnrolledPerson("170", "Visitante Silva", "/face/170.jpg")

            async def fetch_photo(self, reference):
                return b"da-facial"

            async def close(self):
                pass

        class Factory:
            def create(self, device):
                return Directory()

        await ResidentSyncService(self.residents, Factory()).sync(
            Device(1, "Entrada", "10.0.0.1", 80, "admin", None, True)
        )

        self.assertEqual(self.residents.get_photo(self.residents.find(1, "170").id), b"da-facial")

    async def test_the_sigma_photo_does_not_count_as_a_face_on_the_facial(self) -> None:
        """Contada, a verificação periódica veria diferença onde não há e sincronizaria à toa."""
        self.enrol(1, "170", "Visitante Silva")
        await SigmaImportService(self.residents).run(
            FakeClient([dweller("170", "Visitante Silva", sigma_id=900)], {900: b"do-sigma"}), 1
        )

        count = self.residents.enrollment_count(1)

        self.assertEqual((count.users, count.faces), (1, 0))


class SigmaActiveTests(unittest.IsolatedAsyncioTestCase):
    """Quem o Sigma desativou e a facial ainda deixa passar."""

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

    async def test_records_who_sigma_disabled_on_every_enrollment(self) -> None:
        for device_id in (1, 2):
            self.enrol(device_id, "88", "Ex Morador")
        self.enrol(1, "7", "Adna")

        report = await SigmaImportService(self.residents).run(FakeClient([
            dweller("88", "Ex Morador", enabled=False),
            dweller("7", "Adna", enabled=True),
        ]), 1)

        self.assertEqual(report.inactive, 1)
        self.assertIs(self.residents.find(1, "88").active, False)
        self.assertIs(self.residents.find(2, "88").active, False)
        self.assertIs(self.residents.find(1, "7").active, True)
        self.assertIn("1 desativada(s)", outcome_of(report)[1])

    async def test_somebody_sigma_does_not_know_stays_unknown(self) -> None:
        """Nulo não é ativo: o Sigma simplesmente não disse nada sobre a pessoa."""
        self.enrol(1, "5", "Visitante Avulso")

        await SigmaImportService(self.residents).run(FakeClient([]), 1)

        self.assertIsNone(self.residents.find(1, "5").active)

    async def test_the_same_identifier_with_another_name_is_not_touched(self) -> None:
        """ADR 0010: o ID 2 nomeia pessoas diferentes em faciais diferentes."""
        self.enrol(1, "2", "nk")
        self.enrol(2, "2", "Naldo Souza")

        await SigmaImportService(self.residents).run(
            FakeClient([dweller("2", "Naldo Souza", enabled=False)]), 1
        )

        self.assertIsNone(self.residents.find(1, "2").active)
        self.assertIs(self.residents.find(2, "2").active, False)

    async def test_reenabled_in_sigma_is_active_again(self) -> None:
        self.enrol(1, "88", "Ex Morador")
        await SigmaImportService(self.residents).run(
            FakeClient([dweller("88", "Ex Morador", enabled=False)]), 1
        )

        await SigmaImportService(self.residents).run(
            FakeClient([dweller("88", "Ex Morador", enabled=True)]), 1
        )

        self.assertIs(self.residents.find(1, "88").active, True)

    def test_the_search_carries_the_status_to_the_porter(self) -> None:
        from app.application.services.resident_search import group_people

        self.enrol(1, "88", "Ex Morador")
        self.residents.set_active({("88", "Ex Morador"): False})

        [pessoa] = group_people(self.residents.list_directory())

        self.assertIs(pessoa.active, False)
        self.assertIs(self.residents.find(1, "88").to_summary().active, False)


def visitante(sigma_id: int, name: str, enrollment: str = "", **campos) -> SigmaDweller:
    return dweller(enrollment, name, sigma_id=sigma_id, visitor=True, **campos)


class SigmaVisitorTests(unittest.IsolatedAsyncioTestCase):
    """Visitantes cadastrados no Sigma que não estão em facial nenhuma."""

    def setUp(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        self.session = Session(engine)
        self.addCleanup(self.session.close)
        self.residents = SqlAlchemyResidentRepository(self.session)

    async def visitors(self, visitantes, photos=None):
        client = FakeClient([], photos, visitantes=visitantes)
        return await SigmaImportService(self.residents).run_visitors(client, 1), client

    def sigma_only(self):
        return [r for r in self.residents.list_directory() if r.device_id is None]

    async def test_brings_an_active_visitor_into_the_directory(self) -> None:
        report, _ = await self.visitors(
            [visitante(501, "Carlos Visita", apartment="301", block="A", cpf="123")],
            {501: b"\xff\xd8\xffv"},
        )

        [row] = self.sigma_only()
        self.assertEqual((row.name, row.apartment, row.block, row.cpf), ("Carlos Visita", "301", "A", "123"))
        self.assertTrue(row.has_photo)
        self.assertIs(row.active, True)
        self.assertEqual((report.created, report.photos), (1, 1))

    async def test_the_porter_finds_the_visitor(self) -> None:
        from app.application.services.resident_search import search

        await self.visitors([visitante(501, "Carlos Visita", apartment="301")])

        [pessoa] = search(self.residents.list_directory(), "carlos")
        self.assertEqual((pessoa.name, pessoa.device_ids), ("Carlos Visita", ()))

    async def test_a_disabled_visitor_is_not_brought_in(self) -> None:
        await self.visitors([visitante(501, "Carlos Visita", enabled=False)])

        self.assertEqual(self.sigma_only(), [])

    async def test_a_visitor_disabled_later_is_removed(self) -> None:
        await self.visitors([visitante(501, "Carlos Visita")])

        report, _ = await self.visitors([visitante(501, "Carlos Visita", enabled=False)])

        self.assertEqual((report.removed, self.sigma_only()), (1, []))

    async def test_running_again_updates_instead_of_duplicating(self) -> None:
        await self.visitors([visitante(501, "Carlos Visita", apartment="301")])

        report, _ = await self.visitors([visitante(501, "Carlos Visita", apartment="402")])

        [row] = self.sigma_only()
        self.assertEqual((row.apartment, report.created, report.updated), ("402", 0, 1))

    async def test_asks_for_the_photo_only_the_first_time(self) -> None:
        """Quem o Sigma não tem foto não pode ser perguntado a cada verificação."""
        await self.visitors([visitante(501, "Carlos Visita")])

        _, client = await self.visitors([visitante(501, "Carlos Visita")])

        self.assertEqual(client.photo_requests, [])

    async def test_a_visitor_already_on_a_facial_is_left_to_that_enrollment(self) -> None:
        """A mesma pessoa não pode aparecer duas vezes para o porteiro."""
        self.residents.save_enrollment(1, EnrolledPerson("170", "Carlos Visita", None), photo=None)

        await self.visitors([visitante(501, "Carlos Visita", enrollment="170")])

        self.assertEqual(self.sigma_only(), [])

    async def test_a_visitor_enrolled_on_a_facial_later_leaves_the_sigma_only_row(self) -> None:
        await self.visitors([visitante(501, "Carlos Visita", enrollment="170")])
        self.residents.save_enrollment(1, EnrolledPerson("170", "Carlos Visita", None), photo=None)

        report, _ = await self.visitors([visitante(501, "Carlos Visita", enrollment="170")])

        self.assertEqual((report.removed, self.sigma_only()), (1, []))

    async def test_the_full_import_enriches_a_visitor_on_a_facial(self) -> None:
        """Antes, só moradores eram lidos, e o visitante na facial ficava sem nada."""
        self.residents.save_enrollment(1, EnrolledPerson("170", "Carlos Visita", None), photo=None)
        client = FakeClient([], visitantes=[
            visitante(501, "Carlos Visita", enrollment="170", apartment="301"),
            visitante(502, "Sem Facial"),
        ])

        report = await SigmaImportService(self.residents).run(client, 1)

        self.assertEqual(self.residents.find(1, "170").apartment, "301")
        self.assertIs(self.residents.find(1, "170").active, True)
        self.assertEqual([r.name for r in self.sigma_only()], ["Sem Facial"])
        # Visitante fora das faciais não é "não encontrado": ele foi importado.
        self.assertEqual(report.unmatched, [])
        self.assertIn("Visitantes sem facial: 1 no pMoni (1 novos)", outcome_of(report)[1])

    async def test_a_sigma_only_visitor_is_not_mistaken_for_a_facial(self) -> None:
        """Contada como facial, a verificação periódica veria diferença e sincronizaria à toa."""
        await self.visitors([visitante(501, "Carlos Visita")])

        self.assertEqual(self.residents.enrollment_count(1).users, 0)


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
