from alembic import command
from alembic.config import Config

from app.core.config import settings
from app.core.paths import bundle_root


def init_database():
    """
    Bring the database up to the current schema.

    Migrations still own every schema change — nothing here creates tables on its
    own. What changed is who runs them: an installed copy has no one to type
    `alembic upgrade head`, and the first start on a new machine has no database at
    all, so applying the pending revisions is part of starting up.
    """
    config = Config(str(bundle_root() / "alembic.ini"))
    # The paths inside the file are relative to the backend directory, which is not
    # where the packaged program runs from.
    config.set_main_option("script_location", str(bundle_root() / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    command.upgrade(config, "head")
