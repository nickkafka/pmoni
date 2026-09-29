import unittest
from datetime import time
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.application.services.daily_import import DailyImportScheduler
from app.core.config import settings
from app.database.database import Base
from app.domain.entities.automation import ImportStatus
from app.domain.entities.resident import EnrolledPerson, EnrollmentCount
from app.infrastructure.persistence.automation_repository import SqlAlchemyAutomationRepository
from app.domain.entities.sigma import SigmaDweller
from app.infrastructure.persistence.device_repository import SqlAlchemyDeviceRepository
from app.infrastructure.persistence.models import DeviceRecord
from app.infrastructure.persistence.resident_repository import SqlAlchemyResidentRepository
from app.infrastructure.persistence.sigma_repository import SqlAlchemySigmaRepository
from app.infrastructure.security import FernetCredentialCipher
from app.sigma.client import SigmaClient, SigmaUnavailable


class FakeDirectory:
    def __init__(self, people: list[EnrolledPerson], *, explode: bool = False) -> None:
        self._people = people
        self._explode = explode
        self.closed = False
        self.counted = 0
        self.listed = 0
        # Cadastros que o equipamento conta mas a sincronização pula (sem nome).
        self.unlisted = 0

    async def list_enrolled(self):
        if self._explode:
            raise ConnectionError("equipamento fora do ar")
        self.listed += 1
        for person in self._people:
            yield person

    async def count_enrolled(self) -> EnrollmentCount:
        self.counted += 1
        if self._explode:
            raise ConnectionError("equipamento fora do ar")
        faces = sum(1 for person in self._people if person.photo_reference)
        return EnrollmentCount(users=len(self._people) + self.unlisted, faces=faces)

    async def fetch_photo(self, reference: str) -> bytes | None:
        return b"jpeg"

    async def close(self) -> None:
        self.closed = True


class FakeDirectoryFactory:
    """Answers per device, so a run can have one gate up and another down."""

    def __init__(self, by_device: dict[int, FakeDirectory]) -> None:
        self.by_device = by_device

    def create(self, device):
        return self.by_device[device.id]


def offline_sigma(test: unittest.TestCase) -> None:
    """A lista de visitantes nunca sai para a rede num teste."""
    patcher = patch.object(SigmaClient, "visitors", return_value=[])
    patcher.start()
    test.addCleanup(patcher.stop)


def person(employee_no: str, name: str) -> EnrolledPerson:
    return EnrolledPerson(employee_no, name, f"/face/{employee_no}.jpg")


class DailyImportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        offline_sigma(self)
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.session = Session(self.engine)
        self.addCleanup(self.session.close)

    def add_device(self, device_id: int, name: str) -> None:
        self.session.add(
            DeviceRecord(
                id=device_id, name=name, host=f"10.0.0.{device_id}", port=80,
                username="admin", credentials_encrypted="x", enabled=True,
            )
        )
        self.session.commit()

    def scheduler(self, directories: dict[int, FakeDirectory]) -> DailyImportScheduler:
        return DailyImportScheduler(self.sessions, FakeDirectoryFactory(directories))

    def stored(self):
        return SqlAlchemyAutomationRepository(Session(self.engine)).get()

    async def test_imports_every_enabled_device_and_reports_success(self) -> None:
        self.add_device(1, "Entrada")
        self.add_device(2, "Saida")
        directories = {
            1: FakeDirectory([person("7", "Adna")]),
            2: FakeDirectory([person("8", "Davi")]),
        }

        await self.scheduler(directories).run()

        automation = self.stored()
        self.assertEqual(automation.last_status, ImportStatus.OK)
        self.assertIn("2 de 2 equipamentos", automation.last_message)
        self.assertIsNotNone(automation.last_run_at)

    async def test_one_gate_down_is_partial_and_the_others_still_import(self) -> None:
        """Uma facial sem resposta não pode cancelar a importação das demais."""
        self.add_device(1, "Entrada")
        self.add_device(2, "Eclusa")
        directories = {
            1: FakeDirectory([person("7", "Adna")]),
            2: FakeDirectory([], explode=True),
        }

        await self.scheduler(directories).run()

        automation = self.stored()
        self.assertEqual(automation.last_status, ImportStatus.PARTIAL)
        self.assertIn("Eclusa", automation.last_message)
        # Quem respondeu foi gravado, apesar da outra ter falhado.
        from app.infrastructure.persistence.resident_repository import SqlAlchemyResidentRepository

        directory = SqlAlchemyResidentRepository(Session(self.engine)).list_directory()
        self.assertEqual([row.name for row in directory], ["Adna"])

    async def test_every_gate_down_is_a_failure(self) -> None:
        """Todas fora é outro problema, e o operador procura outra causa."""
        self.add_device(1, "Entrada")
        directories = {1: FakeDirectory([], explode=True)}

        await self.scheduler(directories).run()

        self.assertEqual(self.stored().last_status, ImportStatus.FAILED)

    async def test_reports_having_nothing_to_import(self) -> None:
        """Automação ligada sem equipamento nenhum não cumpre o que promete."""
        await self.scheduler({}).run()

        automation = self.stored()
        self.assertEqual(automation.last_status, ImportStatus.FAILED)
        self.assertIn("Nenhum equipamento", automation.last_message)

    async def test_reports_a_gate_whose_client_cannot_even_be_built(self) -> None:
        """Credencial ilegível quebra antes de qualquer rede, e ainda é falha daquela facial."""
        self.add_device(1, "Entrada")

        class Exploding:
            def create(self, device):
                raise RuntimeError("credencial ilegível")

        await DailyImportScheduler(self.sessions, Exploding()).run()

        automation = self.stored()
        self.assertEqual(automation.last_status, ImportStatus.FAILED)
        self.assertIn("Entrada", automation.last_message)

    async def test_a_failure_outside_the_devices_is_recorded_instead_of_escaping(self) -> None:
        """Solta, a exceção some num log e a tela mostraria a execução anterior como a última."""
        with patch.object(
            SqlAlchemyDeviceRepository, "list_enabled", side_effect=RuntimeError("banco fora")
        ):
            await self.scheduler({}).run()

        automation = self.stored()
        self.assertEqual(automation.last_status, ImportStatus.FAILED)
        self.assertIn("banco fora", automation.last_message)
        self.assertIsNotNone(automation.last_run_at)

    async def test_records_the_run_without_disturbing_the_schedule(self) -> None:
        SqlAlchemyAutomationRepository(self.session).save_schedule(
            enabled=True, run_at=time(4, 30)
        )
        self.add_device(1, "Entrada")

        await self.scheduler({1: FakeDirectory([person("7", "Adna")])}).run()

        automation = self.stored()
        self.assertTrue(automation.enabled)
        self.assertEqual(automation.run_at, time(4, 30))


class SigmaStageTests(unittest.IsolatedAsyncioTestCase):
    """A segunda etapa da rotina: buscar no Sigma o que as faciais não sabem."""

    def setUp(self) -> None:
        offline_sigma(self)
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.session = Session(self.engine)
        self.addCleanup(self.session.close)
        self.sigma = SqlAlchemySigmaRepository(self.session)
        # A mesma chave que o serviço usa para decifrar: cifrar com outra faria o
        # teste passar por um caminho de erro em vez do que ele quer exercitar.
        self.cipher = FernetCredentialCipher(settings.DEVICE_CREDENTIALS_KEY)

        self.session.add(
            DeviceRecord(
                id=1, name="Entrada", host="10.0.0.1", port=80, username="admin",
                credentials_encrypted="x", enabled=True,
            )
        )
        self.session.commit()

    def scheduler(self, directories) -> DailyImportScheduler:
        return DailyImportScheduler(self.sessions, FakeDirectoryFactory(directories))

    def configure_sigma(self) -> None:
        self.sigma.save(encrypted_token=self.cipher.encrypt("token"), account_id=1)

    def stored(self):
        return SqlAlchemyAutomationRepository(Session(self.engine)).get()

    async def test_skips_sigma_when_it_was_never_configured(self) -> None:
        """A maior parte do valor da rotina é a sincronização das faciais."""
        directories = {1: FakeDirectory([person("7", "Adna")])}

        await self.scheduler(directories).run()

        automation = self.stored()
        self.assertEqual(automation.last_status, ImportStatus.OK)
        self.assertNotIn("Sigma", automation.last_message)

    async def test_runs_sigma_after_the_facials_and_says_so(self) -> None:
        self.configure_sigma()
        directories = {1: FakeDirectory([person("7", "Adna")])}
        pessoas = [
            SigmaDweller(enrollment="7", name="Adna", apartment="301", block="A",
                         cpf="111", rg="222")
        ]

        with patch.object(SigmaClient, "dwellers", return_value=pessoas):
            await self.scheduler(directories).run()

        automation = self.stored()
        self.assertEqual(automation.last_status, ImportStatus.OK)
        self.assertIn("Sigma:", automation.last_message)
        # A pessoa que a facial acabou de trazer já saiu com apartamento.
        gravado = SqlAlchemyResidentRepository(Session(self.engine)).find(1, "7")
        self.assertEqual(gravado.apartment, "301")
        self.assertEqual(gravado.cpf, "111")

    async def test_a_sigma_that_fails_does_not_erase_the_facial_result(self) -> None:
        self.configure_sigma()
        directories = {1: FakeDirectory([person("7", "Adna")])}

        with patch.object(SigmaClient, "dwellers", side_effect=SigmaUnavailable("token vencido")):
            await self.scheduler(directories).run()

        automation = self.stored()
        self.assertEqual(automation.last_status, ImportStatus.FAILED)
        # O que a facial trouxe continua lá, e a mensagem diz das duas etapas.
        self.assertIn("1 de 1 equipamentos", automation.last_message)
        self.assertIn("token vencido", automation.last_message)
        self.assertIsNotNone(SqlAlchemyResidentRepository(Session(self.engine)).find(1, "7"))

    async def test_the_worst_of_the_two_stages_is_what_the_screen_shows(self) -> None:
        """Faciais boas e Sigma quebrado ainda deixa gente sem apartamento."""
        self.configure_sigma()
        directories = {1: FakeDirectory([person("7", "Adna")])}

        with patch.object(SigmaClient, "dwellers", side_effect=SigmaUnavailable("fora do ar")):
            await self.scheduler(directories).run()

        self.assertEqual(self.stored().last_status, ImportStatus.FAILED)

    async def test_records_the_run_on_the_sigma_panel_too(self) -> None:
        """Quem olha o painel do Sigma quer a data da última importação, venha de onde vier."""
        self.configure_sigma()
        directories = {1: FakeDirectory([person("7", "Adna")])}
        pessoas = [SigmaDweller(enrollment="7", name="Adna", apartment="301",
                                block=None, cpf=None, rg=None)]

        with patch.object(SigmaClient, "dwellers", return_value=pessoas):
            await self.scheduler(directories).run()

        visto = SqlAlchemySigmaRepository(Session(self.engine)).get()
        self.assertIsNotNone(visto.last_import_at)
        self.assertEqual(visto.last_status, ImportStatus.OK)


class FacialCheckTests(unittest.IsolatedAsyncioTestCase):
    """A verificação entre duas noites: sincroniza só a facial cuja contagem mudou."""

    def setUp(self) -> None:
        offline_sigma(self)
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.session = Session(self.engine)
        self.addCleanup(self.session.close)
        for device_id, name in ((1, "Entrada"), (2, "Saida")):
            self.session.add(
                DeviceRecord(
                    id=device_id, name=name, host=f"10.0.0.{device_id}", port=80,
                    username="admin", credentials_encrypted="x", enabled=True,
                )
            )
        self.session.commit()

    def residents(self) -> SqlAlchemyResidentRepository:
        return SqlAlchemyResidentRepository(Session(self.engine))

    def stored(self):
        return SqlAlchemyAutomationRepository(Session(self.engine)).get()

    async def test_syncs_the_facial_that_gained_somebody_and_leaves_the_other_alone(self) -> None:
        """Quem foi cadastrado depois da importação da noite aparece sem esperar a próxima."""
        entrada = FakeDirectory([person("7", "Adna")])
        saida = FakeDirectory([person("8", "Davi")])
        scheduler = DailyImportScheduler(self.sessions, FakeDirectoryFactory({1: entrada, 2: saida}))
        await scheduler.run()
        entrada.listed = saida.listed = 0

        entrada._people.append(person("9", "Bruna"))
        await scheduler.check()

        self.assertEqual(entrada.listed, 1)
        self.assertEqual(saida.listed, 0)
        self.assertIsNotNone(self.residents().find(1, "9"))
        automation = self.stored()
        self.assertIn("Entrada (1 novos", automation.last_check_message)
        self.assertIsNotNone(automation.last_check_at)

    async def test_a_face_added_to_somebody_already_there_is_also_a_difference(self) -> None:
        """Mesmo número de pessoas, mas uma ganhou rosto: sem isso ela seguiria sem foto."""
        entrada = FakeDirectory([EnrolledPerson("7", "Adna", None)])
        scheduler = DailyImportScheduler(
            self.sessions, FakeDirectoryFactory({1: entrada, 2: FakeDirectory([])})
        )
        await scheduler.run()
        entrada.listed = 0

        entrada._people[0] = person("7", "Adna")
        await scheduler.check()

        self.assertEqual(entrada.listed, 1)
        self.assertTrue(self.residents().find(1, "7").has_photo)

    async def test_nothing_changed_means_nothing_synced(self) -> None:
        entrada = FakeDirectory([person("7", "Adna")])
        saida = FakeDirectory([person("8", "Davi")])
        scheduler = DailyImportScheduler(self.sessions, FakeDirectoryFactory({1: entrada, 2: saida}))
        await scheduler.run()
        entrada.listed = saida.listed = 0

        await scheduler.check()

        self.assertEqual((entrada.listed, saida.listed), (0, 0))
        self.assertIn("2 de 2 faciais conferidas", self.stored().last_check_message)

    async def test_an_entry_the_sync_skips_is_not_synced_again_on_every_check(self) -> None:
        """Um cadastro sem nome nunca entra, e a contagem nunca bate por causa dele."""
        entrada = FakeDirectory([person("7", "Adna")])
        entrada.unlisted = 1
        scheduler = DailyImportScheduler(
            self.sessions, FakeDirectoryFactory({1: entrada, 2: FakeDirectory([])})
        )

        await scheduler.check()
        await scheduler.check()
        self.assertEqual(entrada.listed, 1)

        # Mas volta a sincronizar quando a contagem da facial muda de novo.
        entrada._people.append(person("9", "Bruna"))
        await scheduler.check()
        self.assertEqual(entrada.listed, 2)

    async def test_a_gate_that_does_not_answer_is_reported_and_the_others_still_checked(self) -> None:
        saida = FakeDirectory([person("8", "Davi")])
        scheduler = DailyImportScheduler(
            self.sessions,
            FakeDirectoryFactory({1: FakeDirectory([], explode=True), 2: saida}),
        )

        await scheduler.check()

        self.assertIsNotNone(self.residents().find(2, "8"))
        self.assertIn("Sem resposta: Entrada", self.stored().last_check_message)

    async def test_runs_sigma_only_when_somebody_new_arrived(self) -> None:
        cipher = FernetCredentialCipher(settings.DEVICE_CREDENTIALS_KEY)
        SqlAlchemySigmaRepository(self.session).save(
            encrypted_token=cipher.encrypt("token"), account_id=1
        )
        entrada = FakeDirectory([person("7", "Adna")])
        scheduler = DailyImportScheduler(
            self.sessions, FakeDirectoryFactory({1: entrada, 2: FakeDirectory([])})
        )
        pessoas = [SigmaDweller(enrollment="7", name="Adna", apartment="301",
                                block="A", cpf=None, rg=None)]

        with patch.object(SigmaClient, "dwellers", return_value=pessoas) as dwellers:
            await scheduler.check()
            self.assertEqual(dwellers.call_count, 1)
            self.assertIn("Sigma:", self.stored().last_check_message)
            await scheduler.check()
            self.assertEqual(dwellers.call_count, 1)

        self.assertEqual(self.residents().find(1, "7").apartment, "301")

    async def test_checks_the_sigma_visitors_even_when_no_facial_changed(self) -> None:
        """Visitantes são cadastrados no Sigma o dia inteiro, sem passar por facial."""
        cipher = FernetCredentialCipher(settings.DEVICE_CREDENTIALS_KEY)
        SqlAlchemySigmaRepository(self.session).save(
            encrypted_token=cipher.encrypt("token"), account_id=1
        )
        scheduler = DailyImportScheduler(
            self.sessions, FakeDirectoryFactory({1: FakeDirectory([]), 2: FakeDirectory([])})
        )
        visita = SigmaDweller(enrollment="", name="Carlos Visita", apartment="301", block=None,
                              cpf=None, rg=None, sigma_id=501, visitor=True)

        with patch.object(SigmaClient, "visitors", return_value=[visita]), \
                patch.object(SigmaClient, "profile_photo", return_value=None), \
                patch.object(SigmaClient, "dwellers") as dwellers:
            await scheduler.check()

        # Só a etapa leve: a importação inteira dos moradores não rodou.
        dwellers.assert_not_called()
        [row] = [r for r in self.residents().list_directory() if r.device_id is None]
        self.assertEqual(row.name, "Carlos Visita")
        self.assertIn("Visitantes sem facial: 1 no pMoni (1 novos)", self.stored().last_check_message)

    async def test_the_check_does_not_touch_the_nightly_outcome(self) -> None:
        scheduler = DailyImportScheduler(
            self.sessions,
            FakeDirectoryFactory({1: FakeDirectory([person("7", "Adna")]), 2: FakeDirectory([])}),
        )

        await scheduler.check()

        automation = self.stored()
        self.assertIsNone(automation.last_run_at)
        self.assertIsNone(automation.last_status)


class SchedulingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        offline_sigma(self)
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        self.sessions = sessionmaker(bind=engine)
        self.session = Session(engine)
        self.addCleanup(self.session.close)
        self.repository = SqlAlchemyAutomationRepository(self.session)

    async def scheduler(self) -> DailyImportScheduler:
        scheduler = DailyImportScheduler(self.sessions, FakeDirectoryFactory({}))
        await scheduler.start()
        self.addAsyncCleanup(scheduler.stop)
        return scheduler

    async def test_puts_no_job_on_the_calendar_while_disabled(self) -> None:
        self.repository.save_schedule(enabled=False, run_at=time(3, 0))

        scheduler = await self.scheduler()

        self.assertEqual(scheduler._scheduler.get_jobs(), [])

    async def test_schedules_at_the_hour_that_was_saved(self) -> None:
        self.repository.save_schedule(enabled=True, run_at=time(4, 30))

        scheduler = await self.scheduler()

        [job] = scheduler._scheduler.get_jobs()
        self.assertEqual(str(job.trigger.fields[job.trigger.FIELD_NAMES.index("hour")]), "4")
        self.assertEqual(str(job.trigger.fields[job.trigger.FIELD_NAMES.index("minute")]), "30")

    async def test_moving_the_hour_leaves_one_job_behind_not_two(self) -> None:
        """Guardar sem reagendar deixaria a rotina disparando no horário antigo."""
        self.repository.save_schedule(enabled=True, run_at=time(3, 0))
        scheduler = await self.scheduler()

        scheduler.apply(self.repository.save_schedule(enabled=True, run_at=time(5, 15)))

        [job] = scheduler._scheduler.get_jobs()
        self.assertEqual(str(job.trigger.fields[job.trigger.FIELD_NAMES.index("hour")]), "5")

    async def test_turning_it_off_takes_the_job_off_the_calendar(self) -> None:
        self.repository.save_schedule(enabled=True, run_at=time(3, 0))
        scheduler = await self.scheduler()

        scheduler.apply(self.repository.save_schedule(enabled=False, run_at=time(3, 0)))

        self.assertEqual(scheduler._scheduler.get_jobs(), [])


    async def test_schedules_the_check_at_the_interval_that_was_saved(self) -> None:
        self.repository.save_check(enabled=True, interval_minutes=10)

        scheduler = await self.scheduler()

        job = scheduler._scheduler.get_job("verificacao-faciais")
        self.assertEqual(job.trigger.interval.total_seconds(), 600)
        # A importação diária segue desligada: são rotinas independentes.
        self.assertIsNone(scheduler._scheduler.get_job("importacao-diaria"))

    async def test_changing_the_interval_leaves_one_check_behind_not_two(self) -> None:
        self.repository.save_check(enabled=True, interval_minutes=10)
        scheduler = await self.scheduler()

        scheduler.apply(self.repository.save_check(enabled=True, interval_minutes=30))

        [job] = scheduler._scheduler.get_jobs()
        self.assertEqual(job.trigger.interval.total_seconds(), 1800)

    async def test_turning_the_check_off_takes_it_off_the_calendar(self) -> None:
        self.repository.save_check(enabled=True, interval_minutes=10)
        scheduler = await self.scheduler()

        scheduler.apply(self.repository.save_check(enabled=False, interval_minutes=10))

        self.assertEqual(scheduler._scheduler.get_jobs(), [])


if __name__ == "__main__":
    unittest.main()
