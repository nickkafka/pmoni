from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.dependencies import get_admin_sessions, require_admin
from app.application.services.admin_sessions import AdminSessions
from app.schemas.auth import AdminCredentials, AdminSessionRead

router = APIRouter(prefix="/auth", tags=["auth"])

_bearer = HTTPBearer(auto_error=False)


@router.post("/login", response_model=AdminSessionRead)
def login(
    credentials: AdminCredentials, sessions: AdminSessions = Depends(get_admin_sessions)
) -> AdminSessionRead:
    token = sessions.open(credentials.username, credentials.password)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário ou senha inválidos."
        )
    return AdminSessionRead(token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    presented: HTTPAuthorizationCredentials | None = Depends(_bearer),
    sessions: AdminSessions = Depends(get_admin_sessions),
) -> Response:
    sessions.close(presented.credentials if presented else None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/session", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
def check_session() -> Response:
    """Let the interface find out whether the session it holds is still valid."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)
