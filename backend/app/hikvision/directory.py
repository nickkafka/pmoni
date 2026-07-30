from collections.abc import AsyncIterator
from typing import Any

from app.application.ports.person_directory import PersonDirectory
from app.core.logger import logger
from app.domain.entities.resident import EnrolledPerson
from app.hikvision.exceptions import HikvisionProtocolError, HikvisionResourceMissing
from app.hikvision.session import IsapiSession
from app.hikvision.urls import isapi_path


class HikvisionPersonDirectory(PersonDirectory):
    """Reads enrolled people and their photos from the ISAPI user and face libraries.

    Both searches are paged by ``totalMatches`` rather than by ``responseStatusStrg``:
    the face library answers ``OK`` on every page even while entries remain, so
    trusting that field would silently truncate the directory.
    """

    USER_SEARCH_PATH = "/ISAPI/AccessControl/UserInfo/Search?format=json"
    FACE_SEARCH_PATH = "/ISAPI/Intelligent/FDLib/FDSearch?format=json"
    FACE_LIBRARY_TYPE = "blackFD"
    FACE_LIBRARY_ID = "1"
    PAGE_SIZE = 30

    def __init__(self, *, session: IsapiSession, device_id: int) -> None:
        self._session = session
        self._device_id = device_id

    async def list_enrolled(self) -> AsyncIterator[EnrolledPerson]:
        await self._session.open()
        photos = await self._photo_references()
        async for user in self._users():
            employee_no = str(user.get("employeeNo") or "").strip()
            name = str(user.get("name") or "").strip()
            if not employee_no or not name:
                logger.warning("Cadastro incompleto ignorado no dispositivo {}.", self._device_id)
                continue
            yield EnrolledPerson(
                employee_no=employee_no, name=name, photo_reference=photos.get(employee_no)
            )

    async def fetch_photo(self, reference: str) -> bytes | None:
        """Return ``None`` when the device kept no picture for that enrollment.

        A face enrolled from its biometric template alone has no image stored: some
        firmwares omit the URL entirely, others publish one that answers 404. Neither
        is a failure — there is simply nothing to show.
        """
        try:
            photo = await self._session.get_bytes(reference)
        except HikvisionResourceMissing:
            return None
        return photo or None

    async def close(self) -> None:
        await self._session.close()

    async def _users(self) -> AsyncIterator[dict[str, Any]]:
        position, total = 0, None
        while total is None or position < total:
            payload = await self._session.post_json(
                self.USER_SEARCH_PATH,
                {"UserInfoSearchCond": {
                    "searchID": f"monikraft-{self._device_id}",
                    "searchResultPosition": position, "maxResults": self.PAGE_SIZE,
                }},
            )
            result = self._unwrap(payload, "UserInfoSearch")
            total = int(result.get("totalMatches") or 0)
            page = result.get("UserInfo") or []
            if not page:
                return
            for user in page:
                yield user
            position += len(page)

    async def _photo_references(self) -> dict[str, str]:
        """Map each identifier to the stable path of its enrollment photo."""
        references: dict[str, str] = {}
        position, total = 0, None
        while total is None or position < total:
            payload = await self._session.post_json(
                self.FACE_SEARCH_PATH,
                {"searchResultPosition": position, "maxResults": self.PAGE_SIZE,
                 "faceLibType": self.FACE_LIBRARY_TYPE, "FDID": self.FACE_LIBRARY_ID},
            )
            total = int(payload.get("totalMatches") or 0)
            page = payload.get("MatchList") or []
            if not page:
                break
            for match in page:
                employee_no, face_url = str(match.get("FPID") or ""), match.get("faceURL")
                if employee_no and face_url:
                    references[employee_no] = isapi_path(str(face_url))
            position += len(page)
        return references

    @staticmethod
    def _unwrap(payload: dict[str, Any], key: str) -> dict[str, Any]:
        result = payload.get(key)
        if not isinstance(result, dict):
            raise HikvisionProtocolError(f"Resposta ISAPI sem {key}.")
        return result
