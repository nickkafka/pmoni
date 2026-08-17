from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class DeviceRecord(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    credentials_encrypted: Mapped[str] = mapped_column(String(1024), nullable=False)
    model: Mapped[str | None] = mapped_column(String(50))
    device_type: Mapped[str] = mapped_column(String(50), nullable=False, default="hikvision")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SigmaIntegrationRecord(Base):
    """The Sigma connection: which account, with which token, and how it last went.

    One row, always id 1. The token is stored encrypted and never leaves the backend:
    the interface only ever learns whether one is configured.
    """

    __tablename__ = "sigma_integration"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_encrypted: Mapped[str | None] = mapped_column(String(2048))
    account_id: Mapped[int | None] = mapped_column(Integer)
    last_import_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_status: Mapped[str | None] = mapped_column(String(16))
    last_message: Mapped[str | None] = mapped_column(String(1024))


class ImportAutomationRecord(Base):
    """When the daily import runs, and how the last one went.

    One row, always id 1: an installation watches one condominium and runs one
    routine. The outcome lives here rather than only in the log because the operator
    needs to see it on the screen where the schedule is set.
    """

    __tablename__ = "import_automation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    run_at: Mapped[str] = mapped_column(String(5), nullable=False, default="03:00")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_status: Mapped[str | None] = mapped_column(String(16))
    last_message: Mapped[str | None] = mapped_column(String(1024))


class ResidentRecord(Base):
    """One enrollment, as a single device knows it.

    Identifiers are only unique inside the device that issued them: the same number
    names different people on devices enrolled separately, so an enrollment is keyed
    by device and identifier together.

    ``name`` and ``photo`` are owned by the device and overwritten on every sync,
    while ``apartment``, ``block``, ``cpf`` and ``rg`` come from Sigma — or are
    typed in pMoni for whoever Sigma does not know.
    """

    __tablename__ = "residents"
    __table_args__ = (UniqueConstraint("device_id", "employee_no", name="uq_residents_device_employee"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    employee_no: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    apartment: Mapped[str | None] = mapped_column(String(32))
    block: Mapped[str | None] = mapped_column(String(32))
    # Guardados como vieram, com pontuação e tudo. A busca compara só os dígitos,
    # então o porteiro acha a pessoa digitando com ou sem formatação.
    cpf: Mapped[str | None] = mapped_column(String(32))
    rg: Mapped[str | None] = mapped_column(String(32))
    photo: Mapped[bytes | None] = mapped_column(LargeBinary)
    photo_reference: Mapped[str | None] = mapped_column(String(256))
    synced_at: Mapped[datetime | None] = mapped_column(DateTime)
