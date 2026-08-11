import unittest
from datetime import timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.auth import router as auth_router
from app.api.routes.devices import router as devices_router
from app.application.services.admin_sessions import AdminSessions
from app.database.database import Base, get_session
from app.infrastructure.persistence.device_repository import SqlAlchemyDeviceRepository
from app.infrastructure.persistence.models import DeviceRecord


CIFRADA = "gAAAAA-credencial-de-teste-nao-usar"
"""Distinta o bastante para que procurá-la no arquivo exportado não case com o
texto da nota que o próprio arquivo carrega."""


def build(sessions_factory) -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(devices_router)
    app.state.admin_sessions = AdminSessions(
        username="prever", password="prever", lifetime=timedelta(minutes=30)
    )
    app.state.device_manager = None

    def session_override():
        session = sessions_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = session_override
    return app


class DeviceTransferTests(unittest.TestCase):
    def setUp(self) -> None:
        # O TestClient atende numa thread diferente da do teste, e um SQLite em
        # memória comum daria um banco por conexão — cada lado enxergaria o seu.
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.session = Session(self.engine)
        self.addCleanup(self.session.close)
        self.repository = SqlAlchemyDeviceRepository(self.session)

        self.client = TestClient(build(self.sessions))
        token = self.client.post(
            "/auth/login", json={"username": "prever", "password": "prever"}
        ).json()["token"]
        self.client.headers.update({"Authorization": f"Bearer {token}"})

    def add(self, name: str, host: str, port: int = 80, *, enabled: bool = True) -> DeviceRecord:
        record = DeviceRecord(
            name=name, host=host, port=port, username="admin",
            credentials_encrypted=CIFRADA, model="DS-K1T342MFWX", enabled=enabled,
        )
        self.session.add(record)
        self.session.commit()
        return record

    def stored(self) -> dict[str, DeviceRecord]:
        self.session.expire_all()
        return {device.name: device for device in self.repository.list_all()}

    # Exportar -----------------------------------------------------------------

    def test_export_never_carries_the_passwords(self) -> None:
        """Um arquivo em Downloads com a senha de cada portaria desfaz a cifragem toda."""
        self.add("Entrada", "10.0.0.1")

        payload = self.client.get("/devices/export").json()

        [device] = payload["devices"]
        self.assertNotIn("password", device)
        self.assertNotIn("credentials_encrypted", device)
        self.assertNotIn(CIFRADA, str(payload))

    def test_export_includes_the_disabled_ones(self) -> None:
        """Exportar só os ligados devolveria uma configuração que não é a que está no ar."""
        self.add("Entrada", "10.0.0.1")
        self.add("Reserva", "10.0.0.9", enabled=False)

        payload = self.client.get("/devices/export").json()

        self.assertEqual({d["name"] for d in payload["devices"]}, {"Entrada", "Reserva"})

    # Importar -----------------------------------------------------------------

    def test_registers_a_new_device_that_brings_a_password(self) -> None:
        answer = self.client.post(
            "/devices/import",
            json={
                "devices": [
                    {"name": "Entrada", "host": "10.0.0.1", "port": 80,
                     "username": "admin", "password": "segredo"}
                ]
            },
        )

        self.assertEqual(answer.json(), {"created": 1, "updated": 0, "pending": []})
        self.assertIn("Entrada", self.stored())

    def test_hands_back_a_new_device_without_a_password_instead_of_refusing_it(self) -> None:
        """Abrir o JSON para digitar senha à mão era o que tornava a importação ruim."""
        answer = self.client.post(
            "/devices/import",
            json={
                "devices": [
                    {"name": "Entrada", "host": "10.0.0.1", "port": 8000, "username": "admin"}
                ]
            },
        ).json()

        self.assertEqual(answer["created"], 0)
        [pendente] = answer["pending"]
        # Volta inteiro, para a interface reenviar sem o operador redigitar nada
        # além da senha.
        self.assertEqual(pendente["name"], "Entrada")
        self.assertEqual(pendente["host"], "10.0.0.1")
        self.assertEqual(pendente["port"], 8000)
        self.assertEqual(pendente["username"], "admin")

    def test_does_not_register_a_device_it_cannot_reach(self) -> None:
        """Cadastrar sem credencial deixaria o supervisor tentando e falhando sempre."""
        self.client.post(
            "/devices/import",
            json={"devices": [{"name": "Entrada", "host": "10.0.0.1", "username": "admin"}]},
        )

        self.assertEqual(self.stored(), {})

    def test_registers_the_pending_device_when_it_comes_back_with_a_password(self) -> None:
        """O caminho que o pop-up percorre: devolve o pendente com a senha preenchida."""
        first = self.client.post(
            "/devices/import",
            json={"devices": [{"name": "Entrada", "host": "10.0.0.1", "username": "admin"}]},
        ).json()

        completed = [{**first["pending"][0], "password": "segredo"}]
        answer = self.client.post("/devices/import", json=completed).json()

        self.assertEqual((answer["created"], answer["pending"]), (1, []))
        self.assertIn("Entrada", self.stored())

    def test_updates_the_device_already_at_that_address_instead_of_duplicating(self) -> None:
        self.add("Nome Antigo", "10.0.0.1", 80)

        answer = self.client.post(
            "/devices/import",
            json={
                "devices": [
                    {"name": "Nome Novo", "host": "10.0.0.1", "port": 80, "username": "operador"}
                ]
            },
        ).json()

        self.assertEqual((answer["created"], answer["updated"]), (0, 1))
        devices = self.stored()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices["Nome Novo"].username, "operador")

    def test_keeps_the_stored_password_when_the_file_omits_it(self) -> None:
        """O arquivo exportado não traz senha, e reimportá-lo não pode apagar a que existe."""
        self.add("Entrada", "10.0.0.1")

        self.client.post(
            "/devices/import",
            json={"devices": [{"name": "Entrada", "host": "10.0.0.1", "username": "admin"}]},
        )

        kept = self.repository.get_encrypted_credentials(self.stored()["Entrada"].id)
        self.assertEqual(kept, CIFRADA)

    def test_matches_a_disabled_device_rather_than_creating_a_second_one(self) -> None:
        self.add("Reserva", "10.0.0.9", enabled=False)

        answer = self.client.post(
            "/devices/import",
            json={
                "devices": [
                    {"name": "Reserva", "host": "10.0.0.9", "username": "admin", "enabled": True}
                ]
            },
        ).json()

        self.assertEqual((answer["created"], answer["updated"]), (0, 1))
        self.assertEqual(len(self.stored()), 1)

    def test_registers_the_ones_with_a_password_and_holds_back_the_rest(self) -> None:
        answer = self.client.post(
            "/devices/import",
            json={
                "devices": [
                    {"name": "Com senha", "host": "10.0.0.1", "username": "admin", "password": "x"},
                    {"name": "Sem senha", "host": "10.0.0.2", "username": "admin"},
                ]
            },
        ).json()

        self.assertEqual(answer["created"], 1)
        self.assertEqual([p["name"] for p in answer["pending"]], ["Sem senha"])
        self.assertEqual(list(self.stored()), ["Com senha"])

    def test_accepts_a_bare_list_written_by_hand(self) -> None:
        """Exigir o envelope só atrapalha quem está digitando o arquivo."""
        answer = self.client.post(
            "/devices/import",
            json=[{"name": "Entrada", "host": "10.0.0.1", "username": "admin", "password": "x"}],
        )

        self.assertEqual(answer.status_code, 200)
        self.assertEqual(answer.json()["created"], 1)

    def test_a_file_just_exported_imports_back_unchanged(self) -> None:
        self.add("Entrada", "10.0.0.1", 7999)
        self.add("Eclusa", "10.0.0.2", enabled=False)

        exported = self.client.get("/devices/export").json()
        answer = self.client.post("/devices/import", json=exported).json()

        self.assertEqual((answer["created"], answer["updated"], answer["pending"]), (0, 2, []))
        self.assertEqual(len(self.stored()), 2)

    def test_refuses_an_address_that_is_not_one(self) -> None:
        answer = self.client.post(
            "/devices/import",
            json={"devices": [{"name": "Torta", "host": "não é host", "username": "admin"}]},
        )

        self.assertEqual(answer.status_code, 422)


if __name__ == "__main__":
    unittest.main()
