from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.entities.automation import ImportStatus
from app.domain.entities.sigma import SigmaIntegration
from app.infrastructure.persistence.models import SigmaIntegrationRecord

ROW_ID = 1


class SqlAlchemySigmaRepository:
    """Keeps the Sigma connection, with the token on a path of its own.

    ``get`` answers what the interface may see; the token only ever comes out of
    ``encrypted_token``, which the import calls and no route returns.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> SigmaIntegration:
        record = self._record()
        return SigmaIntegration(
            configured=bool(record.token_encrypted),
            account_id=record.account_id,
            last_import_at=record.last_import_at,
            last_status=ImportStatus(record.last_status) if record.last_status else None,
            last_message=record.last_message,
        )

    def encrypted_token(self) -> str | None:
        return self._record().token_encrypted

    def save(self, *, encrypted_token: str | None, account_id: int | None) -> SigmaIntegration:
        """Store the connection. A token of ``None`` keeps the one already saved.

        The interface cannot show what is stored, so it sends an empty field whenever
        the operator is not changing it — clearing the token on every save would wipe
        the connection each time somebody corrected the account number.
        """
        record = self._record()
        if encrypted_token is not None:
            record.token_encrypted = encrypted_token
        record.account_id = account_id
        self._session.commit()
        return self.get()

    def forget_token(self) -> SigmaIntegration:
        record = self._record()
        record.token_encrypted = None
        self._session.commit()
        return self.get()

    def record_import(
        self, *, finished_at: datetime, status: ImportStatus, message: str
    ) -> SigmaIntegration:
        record = self._record()
        record.last_import_at = finished_at
        record.last_status = str(status)
        record.last_message = message[:1024]
        self._session.commit()
        return self.get()

    def _record(self) -> SigmaIntegrationRecord:
        record = self._session.get(SigmaIntegrationRecord, ROW_ID)
        if record is None:
            # Um banco criado por `Base.metadata.create_all`, como nos testes, tem a
            # tabela mas não a linha que a migration insere.
            record = SigmaIntegrationRecord(id=ROW_ID)
            self._session.add(record)
            self._session.commit()
            self._session.refresh(record)
        return record
