import httpx


def digest_auth(username: str, password: str) -> httpx.DigestAuth:
    """Create the authentication strategy used by ISAPI HTTP endpoints."""
    return httpx.DigestAuth(username, password)
