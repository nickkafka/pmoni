"""
Entry point of the packaged program.

Running from the source tree uvicorn is started from the command line and this file
is not used. Inside the executable there is no command line, so the server has to
start itself.
"""

import multiprocessing
import os
import sys
import threading

import uvicorn


def exit_with_parent(parent_pid: int) -> None:
    """
    Follow the window out.

    Closing the window stops this process on the way, but a crash or a kill of the
    window does not. The leftover would keep the port and the database open, and the
    next launch would put a second copy alongside it, polling the same equipment
    twice. So we wait on the parent and go when it goes.
    """
    if sys.platform != "win32":
        return

    import ctypes

    SYNCHRONIZE = 0x00100000
    INFINITE = 0xFFFFFFFF

    kernel32 = ctypes.windll.kernel32
    # A handle is pointer-sized, and ctypes would otherwise assume an int and cut it
    # in half on a 64-bit build.
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

    handle = kernel32.OpenProcess(SYNCHRONIZE, False, parent_pid)
    if not handle:
        # No handle means no way to watch. Better to keep serving than to guess the
        # parent died and quit on a window that is still open.
        return

    kernel32.WaitForSingleObject(handle, INFINITE)
    # Straight out: the window is gone, so there is nobody left to serve and no
    # shutdown worth waiting for.
    os._exit(0)


def main() -> None:
    parent_pid = os.environ.get("PMONI_PARENT_PID")
    if parent_pid:
        threading.Thread(
            target=exit_with_parent, args=(int(parent_pid),), daemon=True
        ).start()

    from app.core.config import settings
    from main import app

    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        # The application already configured loguru, including the file it writes
        # to. Letting uvicorn install its own handlers would both duplicate the
        # console output and lose those lines from the log file.
        log_config=None,
    )


if __name__ == "__main__":
    # Logging is set up with loguru's queue, which pulls in multiprocessing. A
    # frozen executable starts a subprocess by re-running itself, so without this
    # any such subprocess would boot a second application and fight for the port.
    multiprocessing.freeze_support()
    main()
