import unittest
from typing import Any

from app.hikvision.directory import HikvisionPersonDirectory
from app.hikvision.exceptions import HikvisionResourceMissing


class FakeIsapiSession:
    """Reproduces the two paging quirks measured on the DS-K1T342 firmware.

    The user search caps a page at thirty entries whatever ``maxResults`` asks for,
    and the face search returns three entries per page while always reporting ``OK``.
    """

    USER_PAGE_LIMIT = 30
    FACE_PAGE_LIMIT = 3

    def __init__(self, users: list[dict[str, Any]], faces: list[dict[str, Any]]) -> None:
        self.users = users
        self.faces = faces
        self.is_open = False
        self.downloads: list[str] = []
        self.absent: set[str] = set()
        self.unreachable: set[str] = set()

    async def open(self) -> None:
        self.is_open = True

    async def close(self) -> None:
        self.is_open = False

    async def get_bytes(self, path: str) -> bytes:
        if path in self.absent:
            raise HikvisionResourceMissing(f"ISAPI {path} não existe no dispositivo.")
        if path in self.unreachable:
            raise ConnectionError("equipamento inacessível")
        self.downloads.append(path)
        return b"jpeg"

    async def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if "UserInfo" in path:
            condition = payload["UserInfoSearchCond"]
            page = self._page(self.users, condition, self.USER_PAGE_LIMIT)
            return {"UserInfoSearch": {"totalMatches": len(self.users), "UserInfo": page}}
        page = self._page(self.faces, payload, self.FACE_PAGE_LIMIT)
        return {"totalMatches": len(self.faces), "responseStatusStrg": "OK", "MatchList": page}

    @staticmethod
    def _page(rows: list[dict[str, Any]], condition: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        position = condition["searchResultPosition"]
        return rows[position : position + min(condition["maxResults"], limit)]


def user(employee_no: str, name: str) -> dict[str, Any]:
    return {"employeeNo": employee_no, "name": name}


def face(employee_no: str, index: int) -> dict[str, Any]:
    return {
        "FPID": employee_no,
        "faceURL": f"http://device:7999/LOCALS/pic/enrlFace/0/{index:010d}.jpg@WEB00000000000{index}",
    }


class HikvisionPersonDirectoryTests(unittest.IsolatedAsyncioTestCase):
    async def collect(self, session: FakeIsapiSession):
        directory = HikvisionPersonDirectory(session=session, device_id=1)
        return [person async for person in directory.list_enrolled()]

    async def test_reads_every_page_of_both_libraries(self) -> None:
        users = [user(str(index), f"Pessoa {index}") for index in range(55)]
        faces = [face(str(index), index) for index in range(55)]

        people = await self.collect(FakeIsapiSession(users, faces))

        self.assertEqual(len(people), 55)
        self.assertTrue(all(person.photo_reference for person in people))

    async def test_strips_host_and_token_from_the_photo_reference(self) -> None:
        people = await self.collect(FakeIsapiSession([user("2", "nk")], [face("2", 54)]))

        self.assertEqual(people[0].photo_reference, "/LOCALS/pic/enrlFace/0/0000000054.jpg")

    async def test_reports_a_person_without_an_enrolled_face(self) -> None:
        people = await self.collect(FakeIsapiSession([user("2", "nk")], []))

        self.assertIsNone(people[0].photo_reference)
        self.assertEqual(people[0].name, "nk")

    async def test_ignores_a_registration_missing_its_identifier(self) -> None:
        session = FakeIsapiSession([user("", "sem matricula"), user("2", "nk")], [])

        people = await self.collect(session)

        self.assertEqual([person.employee_no for person in people], ["2"])

    async def test_reports_no_picture_when_the_device_answers_404(self) -> None:
        """Rosto cadastrado só pelo template: a URL existe, o arquivo não."""
        session = FakeIsapiSession([user("2", "nk")], [face("2", 54)])
        session.absent.add("/LOCALS/pic/enrlFace/0/0000000054.jpg")
        directory = HikvisionPersonDirectory(session=session, device_id=1)

        self.assertIsNone(await directory.fetch_photo("/LOCALS/pic/enrlFace/0/0000000054.jpg"))

    async def test_still_reports_a_transport_failure(self) -> None:
        session = FakeIsapiSession([user("2", "nk")], [face("2", 54)])
        session.unreachable.add("/face.jpg")
        directory = HikvisionPersonDirectory(session=session, device_id=1)

        with self.assertRaises(ConnectionError):
            await directory.fetch_photo("/face.jpg")

    async def test_fetches_the_photo_from_its_reference(self) -> None:
        session = FakeIsapiSession([user("2", "nk")], [face("2", 54)])
        directory = HikvisionPersonDirectory(session=session, device_id=1)

        photo = await directory.fetch_photo("/LOCALS/pic/enrlFace/0/0000000054.jpg")

        self.assertEqual(photo, b"jpeg")
        self.assertEqual(session.downloads, ["/LOCALS/pic/enrlFace/0/0000000054.jpg"])
