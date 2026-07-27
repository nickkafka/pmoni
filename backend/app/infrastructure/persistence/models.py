from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, LargeBinary, String
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


class ResidentRecord(Base):
    """Person synced from a device, keyed by the identifier shared with Sigma.

    ``name`` and ``photo`` are owned by the device and overwritten on every sync,
    while ``apartment`` and ``block`` are maintained inside Monikraft until Sigma
    supplies them.
    """

    __tablename__ = "residents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    apartment: Mapped[str | None] = mapped_column(String(32))
    block: Mapped[str | None] = mapped_column(String(32))
    photo: Mapped[bytes | None] = mapped_column(LargeBinary)
    photo_reference: Mapped[str | None] = mapped_column(String(256))
    source_device_id: Mapped[int | None] = mapped_column(Integer)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime)
