from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from src.app.core.logging import setup_logging
from src.app.core.middleware import RequestIdMiddleware
from src.app.core.settings import get_settings
from src.app.api.v1.notifications.email import router as email_router
from src.app.api.v1.tasks import router as tasks_router

settings = get_settings()

setup_logging(json_logs=not settings.DEBUG, log_level="INFO")
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application started")
    yield
    logger.info("Application stopped")


app = FastAPI(lifespan=lifespan)
app.add_middleware(RequestIdMiddleware)

app.include_router(email_router)
app.include_router(tasks_router)


@app.get("/ping")
async def hello_world():
    return {"status": "ok", "broker": "rabbitmq"}
