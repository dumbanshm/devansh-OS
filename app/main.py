"""Devansh OS — FastAPI entrypoint.

Wires the generic core together: init DB, import providers (which self-register),
mount the API + static dashboard, and run the background scheduler.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import providers  # noqa: F401  (importing registers every provider)
from .api import api_router
from .config import WEB_DIR, get_settings
from .db import init_db
from .providers.base import registry
from .scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    for provider in registry.all():
        provider.on_startup()
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="Devansh OS", lifespan=lifespan)
app.include_router(api_router)

app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/healthz")
def healthz():
    return {"ok": True}


def main() -> None:
    import uvicorn

    s = get_settings()
    uvicorn.run("app.main:app", host=s.host, port=s.port, reload=False)


if __name__ == "__main__":
    main()
