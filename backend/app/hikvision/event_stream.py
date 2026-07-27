from collections.abc import AsyncIterator

import httpx

from app.hikvision.exceptions import HikvisionProtocolError


async def iter_alert_payloads(response: httpx.Response) -> AsyncIterator[bytes]:
    """Yield complete XML/JSON payloads from a regular or multipart ISAPI stream."""
    content_type = response.headers.get("content-type", "")
    if "multipart/" not in content_type.lower():
        async for chunk in response.aiter_bytes():
            if chunk.strip():
                yield chunk
        return

    boundary = _boundary_from(content_type)
    marker, buffer = b"--" + boundary, b""
    async for chunk in response.aiter_bytes():
        buffer += chunk
        while True:
            first = buffer.find(marker)
            if first < 0:
                buffer = buffer[-len(marker):]
                break
            if first > 0:
                buffer = buffer[first:]
            next_marker = buffer.find(marker, len(marker))
            if next_marker < 0:
                break
            part, buffer = buffer[len(marker):next_marker].strip(b"\r\n"), buffer[next_marker:]
            _, separator, body = part.partition(b"\r\n\r\n")
            if not separator:
                _, separator, body = part.partition(b"\n\n")
            if separator and body.strip():
                yield body.strip()


def _boundary_from(content_type: str) -> bytes:
    for value in content_type.split(";")[1:]:
        key, separator, raw_value = value.strip().partition("=")
        if key.lower() == "boundary" and separator:
            return raw_value.strip().strip('"').lstrip("-").encode()
    raise HikvisionProtocolError("Alert Stream multipart sem boundary.")
