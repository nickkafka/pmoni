import sys
from pathlib import Path

from loguru import logger

LOG_PATH = Path("logs")

LOG_PATH.mkdir(exist_ok=True)

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

logger.add(sys.stdout, level="INFO")
