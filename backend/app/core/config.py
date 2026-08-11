from pathlib import Path

from cryptography.fernet import Fernet
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.paths import data_root


DATA_ROOT = data_root()
DEFAULT_DATABASE_URL = f"sqlite:///{(DATA_ROOT / 'pmoni.db').as_posix()}"
CREDENTIALS_KEY_FILE = DATA_ROOT / "device-credentials.key"


def load_or_create_credentials_key() -> str:
    """
    The key that protects the device passwords, one per installation.

    Shipping a key inside the installer would give every building the same one, and
    asking whoever installs the program to generate a Fernet key by hand is not a
    step that survives contact with a real deployment. So the first start writes one
    next to the database.

    It belongs to the database it encrypted: restoring a backup of one without the
    other leaves the stored passwords unreadable, and the devices simply stop
    authenticating.
    """
    if CREDENTIALS_KEY_FILE.exists():
        return CREDENTIALS_KEY_FILE.read_text(encoding="utf-8").strip()
    key = Fernet.generate_key().decode()
    CREDENTIALS_KEY_FILE.write_text(key, encoding="utf-8")
    return key


class Settings(BaseSettings):
    APP_NAME: str = "pMoni"
    VERSION: str = "0.1.0"

    DATABASE_URL: str = DEFAULT_DATABASE_URL
    DEVICE_CREDENTIALS_KEY: str | None = None

    # Só o próprio computador enxerga a aplicação. A porta é configurável porque
    # 8000 é disputada, e numa máquina onde já existe algo nela a aplicação não
    # subiria.
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000

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
        return f"{prefix}{(DATA_ROOT / database_path).as_posix()}"

    @model_validator(mode="after")
    def ensure_credentials_key(self) -> "Settings":
        # An explicit key in the environment still wins: an installation that
        # already has one must keep reading what it encrypted.
        if not self.DEVICE_CREDENTIALS_KEY:
            self.DEVICE_CREDENTIALS_KEY = load_or_create_credentials_key()
        return self

    model_config = SettingsConfigDict(
        env_file=DATA_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )


settings = Settings()
