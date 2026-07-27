from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.system import router as system_router
from app.api.routes.devices import router as devices_router
from app.api.routes.residents import router as residents_router
from app.core.config import settings
from app.core.logger import logger
from app.database.init_db import init_database
from app.core.runtime import ApplicationRuntime
from app.websocket.access_events import router as access_events_router


runtime = ApplicationRuntime()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando Monikraft...")
    init_database()
    logger.info("Banco de dados inicializado.")
    await runtime.start(app)
    yield
    await runtime.stop()
    logger.info("Finalizando Monikraft...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

app.include_router(system_router)
app.include_router(devices_router)
app.include_router(residents_router)
app.include_router(access_events_router)


@app.get("/")
async def root():
    return {
        "application": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
    }
