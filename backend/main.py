from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.interface import mount_interface
from app.api.routes.auth import router as auth_router
from app.api.routes.automation import router as automation_router
from app.api.routes.system import router as system_router
from app.api.routes.devices import router as devices_router
from app.api.routes.residents import router as residents_router
from app.api.routes.sigma import router as sigma_router
from app.api.routes.snapshots import router as snapshots_router
from app.core.config import settings
from app.core.logger import logger
from app.database.init_db import init_database
from app.core.runtime import ApplicationRuntime
from app.websocket.access_events import router as access_events_router


runtime = ApplicationRuntime()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando pMoni...")
    init_database()
    logger.info("Banco de dados inicializado.")
    await runtime.start(app)
    yield
    await runtime.stop()
    logger.info("Finalizando pMoni...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

app.include_router(system_router)
app.include_router(auth_router)
app.include_router(automation_router)
app.include_router(devices_router)
app.include_router(residents_router)
app.include_router(sigma_router)
app.include_router(snapshots_router)
app.include_router(access_events_router)

# Last: the interface answers every path the routers above did not take. `/health`
# already reports name, version and status, which is all the old root route said.
mount_interface(app)
