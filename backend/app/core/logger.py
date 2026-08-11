import sys

from loguru import logger

from app.core.paths import data_root

# Anchored to the data directory rather than the working directory: the installed
# program is started from a shortcut, and whatever directory that leaves us in is
# not somewhere we may write.
LOG_PATH = data_root() / "logs"

LOG_PATH.mkdir(parents=True, exist_ok=True)

# The Windows console runs on cp1252 and cannot encode the symbols loguru uses for
# levels and tracebacks. Without this, every error turns into a logging failure and
# the original message is lost exactly when it is needed.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logger.remove()

logger.add(
    LOG_PATH / "pmoni.log",
    rotation="10 MB",
    retention="30 days",
    level="INFO",
    enqueue=True,
    encoding="utf-8",
)

# The packaged program may run without a console, and then there is no stream to
# write to. The file handler above is what matters there.
if sys.stdout is not None:
    logger.add(sys.stdout, level="INFO")
