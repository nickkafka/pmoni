from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.services.admin_sessions import AdminSessions

_bearer = HTTPBearer(auto_error=False)


def get_admin_sessions(request: Request) -> AdminSessions:
    sessions: AdminSessions | None = getattr(request.app.state, "admin_sessions", None)
    if sessions is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administração indisponível.",
        )
    return sessions


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    sessions: AdminSessions = Depends(get_admin_sessions),
) -> None:
    """Guard the administration routes.

    Without this the login screen would only hide the interface: the same
    endpoints answer anyone able to reach the API.
    """
    if not sessions.holds(credentials.credentials if credentials else None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Faça login para administrar.",
            headers={"WWW-Authenticate": "Bearer"},
        )
