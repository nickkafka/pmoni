# -*- mode: python ; coding: utf-8 -*-
"""
Packaging of the backend into a self-contained executable.

Built as a directory rather than a single file on purpose: a one-file build unpacks
itself into a temporary folder on every start, which costs seconds the porter screen
would spend staring at nothing, and leaves the migration scripts at a path that
changes between runs.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

BACKEND = Path(SPECPATH)
FRONTEND_BUILD = BACKEND.parent / "frontend" / "dist"

if not (FRONTEND_BUILD / "index.html").is_file():
    raise SystemExit(
        f"Interface não encontrada em {FRONTEND_BUILD}. "
        "Rode `npm run build` no diretório frontend antes de empacotar."
    )

datas = [
    # Alembic reads these as files at runtime, so they travel as data rather than
    # as imported modules.
    (str(BACKEND / "alembic.ini"), "."),
    (str(BACKEND / "alembic"), "alembic"),
    (str(FRONTEND_BUILD), "frontend"),
]

hiddenimports = [
    # Each of these is reached by name at runtime instead of by an import
    # statement, so the analysis cannot see them: uvicorn picks its event loop and
    # protocol implementations, SQLAlchemy and Alembic pick the SQLite dialect, and
    # APScheduler picks trigger and executor classes.
    *collect_submodules("uvicorn"),
    *collect_submodules("alembic"),
    *collect_submodules("apscheduler"),
    *collect_submodules("sqlalchemy.dialects"),
    # Imported only by the Alembic environment, which is a data file here.
    "app.infrastructure.persistence.models",
]

a = Analysis(
    ["launcher.py"],
    pathex=[str(BACKEND)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="pmoni-backend",
    debug=False,
    strip=False,
    upx=False,
    # Kept as a console program so it still has somewhere to write. Electron starts
    # it with the window hidden, so nothing shows up on screen.
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="pmoni-backend",
)
