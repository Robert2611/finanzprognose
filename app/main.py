"""App factory and the production app instance.

`create_app(settings)` builds an independent app: its own database, backup directory,
status file, auth and scheduler, all taken from `settings`. `app` is the instance
uvicorn serves in production (`uvicorn app.main:app`), configured from the environment.
"""
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import auth, backup_schedule, db, errors
from .routes import router
from .settings import Settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s: Settings = app.state.settings
    db.init(s.db_path)
    stop = backup_schedule.start_scheduler(s) if s.backup_scheduler else None
    try:
        yield
    finally:
        if stop is not None:
            stop.set()


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    app = FastAPI(title="Finanzprognose", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)
    app.state.settings = settings or Settings.from_env()
    app.middleware("http")(auth.basic_auth)
    errors.register(app)
    app.include_router(router)
    # Mounted last: API routes must be registered before the catch-all static mount.
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
