from app.database.database import engine
from sqlalchemy import inspect


def init_database():
    """Ensure migrations, not application startup, own schema changes."""
    if "alembic_version" not in inspect(engine).get_table_names():
        raise RuntimeError(
            "O banco de dados não está migrado. Execute `alembic upgrade head` no diretório backend."
        )
