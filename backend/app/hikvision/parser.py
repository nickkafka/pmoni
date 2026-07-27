import json
from datetime import UTC, datetime
from typing import Any
from xml.etree import ElementTree

from app.domain.entities.access_event import AccessEvent
from app.hikvision.exceptions import HikvisionEventParseError


class HikvisionAlertParser:
    """Converts XML/JSON ISAPI notifications into Monikraft domain events."""

    def parse(self, payload: bytes, device_id: int) -> AccessEvent | None:
        data = self._decode(payload)
        event_data = self._find_access_data(data)
        if event_data is None or self._is_heartbeat(event_data):
            return None
        event_time = self._event_time(event_data)
        employee_no = self._first_value(event_data, "employeeNoString", "employeeNo", "personId")
        external_id = self._first_value(event_data, "serialNo", "UUID", "eventId", "eventID")
        if external_id is None:
            external_id = f"{device_id}:{event_time.isoformat()}:{employee_no or 'unknown'}"
        return AccessEvent(
            external_id=str(external_id), device_id=device_id,
            employee_no=str(employee_no) if employee_no is not None else None,
            access_type=str(self._first_value(event_data, "currentVerifyMode", "verifyMode", "eventType") or "unknown"),
            success=self._success(event_data), event_time=event_time,
            snapshot=self._first_value(event_data, "pictureURL", "pictureUrl", "imageURL", "imageUrl"),
        )

    def _decode(self, payload: bytes) -> dict[str, Any]:
        content = payload.strip().lstrip(b"\xef\xbb\xbf")
        if not content:
            raise HikvisionEventParseError("Notificação ISAPI vazia.")
        try:
            if content.startswith((b"{", b"[")):
                parsed = json.loads(content)
                return parsed if isinstance(parsed, dict) else {"events": parsed}
            root = ElementTree.fromstring(content)
        except (json.JSONDecodeError, ElementTree.ParseError) as exc:
            raise HikvisionEventParseError("Notificação ISAPI inválida.") from exc
        return {self._local_name(root.tag): self._xml_to_dict(root)}

    def _find_access_data(self, data: dict[str, Any]) -> dict[str, Any] | None:
        for candidate in self._walk_dicts(data):
            event_type = str(candidate.get("eventType", "")).lower()
            if "access" in event_type or "face" in event_type or "employeeNoString" in candidate:
                return candidate
        return None

    @staticmethod
    def _is_heartbeat(data: dict[str, Any]) -> bool:
        return str(data.get("eventType", "")).lower() == "videoloss" and str(data.get("eventState", "")).lower() == "inactive"

    def _event_time(self, data: dict[str, Any]) -> datetime:
        value = self._first_value(data, "dateTime", "time", "eventTime")
        if value is None:
            raise HikvisionEventParseError("Evento de acesso sem data e hora.")
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise HikvisionEventParseError("Data e hora ISAPI inválida.") from exc
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed

    def _success(self, data: dict[str, Any]) -> bool:
        value = self._first_value(data, "success", "isSuccess", "status", "eventState")
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"true", "1", "success", "succeeded", "ok", "active", "normal"}

    @staticmethod
    def _first_value(data: dict[str, Any], *keys: str) -> Any | None:
        for item in HikvisionAlertParser._walk_dicts(data):
            for key in keys:
                value = item.get(key)
                if value not in (None, ""):
                    return value
        return None

    @staticmethod
    def _walk_dicts(value: Any):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from HikvisionAlertParser._walk_dicts(child)
        elif isinstance(value, list):
            for child in value:
                yield from HikvisionAlertParser._walk_dicts(child)

    def _xml_to_dict(self, element: ElementTree.Element) -> Any:
        children = list(element)
        if not children:
            return (element.text or "").strip()
        result: dict[str, Any] = {}
        for child in children:
            name, value = self._local_name(child.tag), self._xml_to_dict(child)
            if name in result:
                result[name] = result[name] if isinstance(result[name], list) else [result[name]]
                result[name].append(value)
            else:
                result[name] = value
        return result

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]
