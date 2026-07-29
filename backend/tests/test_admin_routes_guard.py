import unittest
from datetime import timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auth import router as auth_router
from app.api.routes.devices import router as devices_router
from app.api.routes.residents import router as residents_router
from app.api.routes.snapshots import router as snapshots_router
from app.application.services.admin_sessions import AdminSessions
from app.websocket.access_events import router as access_events_router


def credentials(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build() -> FastAPI:
    """Only the routes, without the device supervisors the real startup opens."""
    app = FastAPI()
    for router in (auth_router, devices_router, residents_router, snapshots_router, access_events_router):
        app.include_router(router)
    app.state.admin_sessions = AdminSessions(
        username="prever", password="prever", lifetime=timedelta(minutes=30)
    )
    app.state.access_events = None
    app.state.snapshots = None
    return app


class AdminGuardTests(unittest.TestCase):
    """The screen alone would protect nothing: these routes answer anyone able to
    reach the API, so the guard has to live here."""

    def setUp(self) -> None:
        self.client = TestClient(build())

    def login(self) -> str:
        answer = self.client.post("/auth/login", json={"username": "prever", "password": "prever"})
        self.assertEqual(answer.status_code, 200)
        return answer.json()["token"]

    def test_refuses_the_administration_routes_without_a_session(self) -> None:
        for method, path in (
            ("GET", "/devices"),
            ("POST", "/devices"),
            ("PATCH", "/devices/1"),
            ("DELETE", "/devices/1"),
            ("GET", "/residents"),
            ("PATCH", "/residents/1"),
            ("DELETE", "/residents"),
            ("POST", "/residents/sync/1"),
        ):
            with self.subTest(route=f"{method} {path}"):
                answer = self.client.request(method, path, json={})
                self.assertEqual(answer.status_code, 401)

    def test_refuses_a_made_up_token(self) -> None:
        self.assertEqual(self.client.get("/devices", headers=credentials("inventado")).status_code, 401)

    def test_allows_the_administration_routes_after_login(self) -> None:
        self.assertEqual(self.client.get("/devices", headers=credentials(self.login())).status_code, 200)

    def test_refuses_wrong_credentials(self) -> None:
        answer = self.client.post("/auth/login", json={"username": "prever", "password": "errada"})

        self.assertEqual(answer.status_code, 401)

    def test_logout_ends_the_session(self) -> None:
        token = self.login()

        self.client.post("/auth/logout", headers=credentials(token))

        self.assertEqual(self.client.get("/devices", headers=credentials(token)).status_code, 401)

    def test_confirms_a_session_the_interface_still_holds(self) -> None:
        self.assertEqual(
            self.client.get("/auth/session", headers=credentials(self.login())).status_code, 204
        )

    def test_keeps_the_porter_screen_open(self) -> None:
        """The booth has nobody to type a password when the machine starts."""
        with self.client.websocket_connect("/ws/access-events") as socket:
            self.assertEqual(socket.receive_json()["type"], "system_status")
        self.assertEqual(self.client.get("/residents/999999/photo").status_code, 404)
        self.assertEqual(self.client.get("/access-events/1/x/snapshot").status_code, 404)
