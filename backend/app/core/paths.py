"""
Where the application reads from and where it writes to.

Running from the source tree both answers are the `backend` directory, which is why
the rest of the code could ignore the distinction so far. Inside the installed
program they are different places: the code and the migration scripts live under
`Program Files`, where a standard user cannot write, so the database, the logs and
the configuration have to go somewhere else.
"""

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]

APPLICATION_DIRECTORY = "pMoni"


def is_frozen() -> bool:
    """True when running from the packaged executable rather than the source tree."""
    return getattr(sys, "frozen", False)


def bundle_root() -> Path:
    """
    Files shipped with the program and never written to: migration scripts and the
    built interface. PyInstaller unpacks them next to the executable and points
    `_MEIPASS` at that directory.
    """
    if is_frozen():
        return Path(sys._MEIPASS)
    return BACKEND_ROOT


def frontend_root() -> Path:
    """
    The built interface. Only the packaged program serves it from here — during
    development Vite serves the interface itself, and this directory holds whatever
    the last `npm run build` left behind.
    """
    if is_frozen():
        return bundle_root() / "frontend"
    return BACKEND_ROOT.parent / "frontend" / "dist"


def data_root() -> Path:
    """
    Everything the installation accumulates: database, logs, configuration and the
    key that protects the device credentials. Kept per user, so an operator without
    administrator rights can still run the program.
    """
    if not is_frozen():
        return BACKEND_ROOT
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    directory = base / APPLICATION_DIRECTORY
    directory.mkdir(parents=True, exist_ok=True)
    return directory
