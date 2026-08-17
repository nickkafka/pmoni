from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.application.services.sigma_import import SigmaImportService, outcome_of
from app.core.config import settings
from app.core.logger import logger
from app.database.database import get_session
from app.domain.entities.automation import ImportStatus
from app.infrastructure.persistence.resident_repository import SqlAlchemyResidentRepository
from app.infrastructure.persistence.sigma_repository import SqlAlchemySigmaRepository
from app.infrastructure.security import CredentialProtectionUnavailable, FernetCredentialCipher
from app.schemas.sigma import (
    SigmaAccountRead,
    SigmaImportRead,
    SigmaIntegrationRead,
    SigmaSettingsUpdate,
)
from app.sigma.client import SigmaClient, SigmaUnavailable

router = APIRouter(prefix="/sigma", tags=["sigma"], dependencies=[Depends(require_admin)])


def get_repository(session: Session = Depends(get_session)) -> SqlAlchemySigmaRepository:
    return SqlAlchemySigmaRepository(session)


def _cipher() -> FernetCredentialCipher:
    try:
        return FernetCredentialCipher(settings.DEVICE_CREDENTIALS_KEY)
    except CredentialProtectionUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


def _open_client(repository: SqlAlchemySigmaRepository) -> SigmaClient:
    encrypted = repository.encrypted_token()
    if not encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe o token da Segware antes de consultar o Sigma.",
        )
    return SigmaClient(_cipher().decrypt(encrypted))


@router.get("", response_model=SigmaIntegrationRead)
def read_settings(
    repository: SqlAlchemySigmaRepository = Depends(get_repository),
) -> SigmaIntegrationRead:
    return SigmaIntegrationRead.of(repository.get())


@router.put("", response_model=SigmaIntegrationRead)
def save_settings(
    payload: SigmaSettingsUpdate,
    repository: SqlAlchemySigmaRepository = Depends(get_repository),
) -> SigmaIntegrationRead:
    """Store the token encrypted, with the same key that protects the device passwords.

    An empty token means "leave the saved one alone": the interface cannot read what
    is stored, so it has nothing to send back when the operator is only correcting
    the account.
    """
    encrypted = _cipher().encrypt(payload.token) if payload.token else None
    return SigmaIntegrationRead.of(
        repository.save(encrypted_token=encrypted, account_id=payload.account_id)
    )


@router.delete("/token", response_model=SigmaIntegrationRead)
def forget_token(
    repository: SqlAlchemySigmaRepository = Depends(get_repository),
) -> SigmaIntegrationRead:
    """Drop the stored token, for when it is rotated or the integration is retired."""
    return SigmaIntegrationRead.of(repository.forget_token())


@router.get("/accounts", response_model=list[SigmaAccountRead])
async def list_accounts(
    repository: SqlAlchemySigmaRepository = Depends(get_repository),
) -> list[SigmaAccountRead]:
    """The accounts the token reaches, so the operator picks instead of typing an id."""
    client = _open_client(repository)
    try:
        contas = await client.accounts()
    except SigmaUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    finally:
        await client.close()
    return [
        SigmaAccountRead(
            id=conta.get("id"),
            name=conta.get("tradeName") or conta.get("name"),
            code=str(conta["accountCode"]) if conta.get("accountCode") is not None else None,
        )
        for conta in contas
        if conta.get("id") is not None
    ]


@router.post("/import", response_model=SigmaImportRead)
async def import_from_sigma(
    session: Session = Depends(get_session),
    repository: SqlAlchemySigmaRepository = Depends(get_repository),
) -> SigmaImportRead:
    """Copy apartment, block, CPF and RG from Sigma onto the local register."""
    integration = repository.get()
    if integration.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Escolha a conta do Sigma antes de importar.",
        )

    client = _open_client(repository)
    service = SigmaImportService(SqlAlchemyResidentRepository(session))
    try:
        report = await service.run(client, integration.account_id)
    except SigmaUnavailable as exc:
        repository.record_import(
            finished_at=datetime.now(), status=ImportStatus.FAILED, message=str(exc)
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("A importação do Sigma falhou.")
        repository.record_import(
            finished_at=datetime.now(),
            status=ImportStatus.FAILED,
            message=f"Falha inesperada: {exc}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Falha inesperada: {exc}"
        ) from exc
    finally:
        await client.close()

    outcome, message = outcome_of(report)
    repository.record_import(finished_at=datetime.now(), status=outcome, message=message)
    return SigmaImportRead(
        status=outcome,
        message=message,
        read=report.read,
        updated=report.updated,
        unmatched=report.unmatched,
    )
