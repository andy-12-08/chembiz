import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.router_registry import register_routers
from backend.logging_setup import configure_logging
from backend.agents.deepsearch.checkpointer import (
    close_deepsearch_checkpointer,
    init_deepsearch_checkpointer,
)
from database.db import engine_dispose, engine_init

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and release process-wide API resources.

    Args:
        app: FastAPI application whose startup and shutdown are being managed.

    Yields:
        Control while the database engine and LangGraph checkpointer are available.
    """
    await engine_init()
    await init_deepsearch_checkpointer()
    logger.info(f"Application startup title={app.title}")
    yield
    await close_deepsearch_checkpointer()
    await engine_dispose()
    logger.info(f"Application shutdown")


app = FastAPI(title="chembiz", lifespan=lifespan)

register_routers(app)


@app.get("/health")
def health() -> dict[str, str]:
    """Report whether the API process is responsive.

    Returns:
        A minimal status payload used by callers and container health checks.
    """
    return {"status": "ok"}
