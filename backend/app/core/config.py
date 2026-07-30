from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = f"sqlite:///{(BACKEND_ROOT / 'monikraft.db').as_posix()}"


class Settings(BaseSettings):
    APP_NAME: str = "pMoni"
    VERSION: str = "0.1.0"

    DATABASE_URL: str = DEFAULT_DATABASE_URL
    DEVICE_CREDENTIALS_KEY: str | None = None

    # Pause between journal queries. The device answers a query in about a second on
    # the local network and more over the internet, so lowering this only helps up to
    # the point where the queries themselves become the limit.
    DEVICE_POLL_INTERVAL_SECONDS: float = 1.0

    # Acesso à administração. As rotas de portaria seguem abertas: a tela da
    # guarita precisa subir sozinha, sem ninguém para digitar uma senha.
    ADMIN_USERNAME: str = "prever"
    ADMIN_PASSWORD: str = "prever"
    ADMIN_SESSION_MINUTES: int = 30

    LOG_LEVEL: str = "INFO"

    @field_validator("DATABASE_URL")
    @classmethod
    def resolve_relative_sqlite_path(cls, database_url: str) -> str:
        prefix = "sqlite:///"
        if not database_url.startswith(prefix) or database_url.endswith(":memory:"):
            return database_url
        database_path = Path(database_url.removeprefix(prefix))
        if database_path.is_absolute():
            return database_url
        return f"{prefix}{(BACKEND_ROOT / database_path).as_posix()}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )


settings = Settings()
