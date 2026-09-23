"""Main FastAPI application."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from .config import ENABLE_DOCS
from .routes import auth, birthdays, settings
from .auth import ensure_default_admin
from .storage import migrate_birthdays_add_ids
from .scheduler import start_scheduler, stop_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start-up and shut-down, replacing the deprecated @app.on_event hooks.

    Everything before the yield runs once as the application starts;
    everything after it runs as the application stops.
    """
    ensure_default_admin()
    migrate_birthdays_add_ids()
    start_scheduler()

    yield

    stop_scheduler()


# Create app. The interactive docs and the OpenAPI schema they are built from
# are disabled unless BIRTHDAYS_ENABLE_DOCS is set; openapi_url has to go too,
# or the schema stays readable even with the UIs switched off.
app = FastAPI(
    title="Birthday Tracker",
    description="A simple birthday tracker with email reminders",
    version="1.0.0",
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
    lifespan=lifespan,
)

# Include routers
app.include_router(auth.router)
app.include_router(birthdays.router)
app.include_router(settings.router)

# Served with "no-cache", which means revalidate before use -- not "do not
# store". Responses already carry an ETag, so an unchanged file costs a 304
# with no body.
#
# Without this there is no Cache-Control header at all, and browsers fall back
# to heuristic caching. They generally revalidate the HTML document when you
# navigate but not its subresources, so after a deploy you could get the new
# index.html together with a stale app.js -- new markup driven by old code,
# where a button exists but nothing is listening to it.
REVALIDATE = "no-cache"


class RevalidatedStaticFiles(StaticFiles):
    """StaticFiles that asks browsers to revalidate rather than guess."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = REVALIDATE
        return response


# Static files
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount(
        "/static", RevalidatedStaticFiles(directory=str(static_path)), name="static"
    )


@app.get("/")
async def root():
    """Serve the main application."""
    index_path = static_path / "index.html"
    if index_path.exists():
        # Same reasoning as the static mount: the document must never be
        # served from cache without checking, or it drifts out of step with
        # the scripts it loads.
        return FileResponse(index_path, headers={"Cache-Control": REVALIDATE})
    return {"message": "Birthday Tracker API"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
