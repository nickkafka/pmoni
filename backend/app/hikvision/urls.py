from urllib.parse import urlsplit


def isapi_path(url: str) -> str:
    """Reduce a picture URL to the path the device session can fetch.

    The firmware answers with the address it knows itself by — a LAN address even
    when the device is reached through a DDNS name — and appends a per-request
    token. Neither survives outside the device, so only the path is kept.
    """
    return urlsplit(url.split("@", 1)[0]).path
