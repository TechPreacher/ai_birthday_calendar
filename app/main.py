"""Main FastAPI application."""

import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from .routes import auth, birthdays, settings
from .auth import ensure_default_admin
from .storage import migrate_birthdays_add_ids
from .scheduler import start_scheduler, stop_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Create app
app = FastAPI(
    title="Birthday Tracker",
    description="A simple birthday tracker with email reminders",
    version="1.0.0",
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


@app.on_event("startup")
async def startup():
    """Run on application startup."""
    ensure_default_admin()
    migrate_birthdays_add_ids()
    start_scheduler()


@app.on_event("shutdown")
async def shutdown():
    """Run on application shutdown."""
    stop_scheduler()


@app.get("/")
async def root():
    """Serve the main application."""
    index_path = static_path / "index.html"
    if index_path.exists():
        # Same reasoning as the static mount: the document must never be
        # served from cache without checking, or it drifts out of step with
        # the scripts it loads.
        return FileResponse(index_path, headers={"Cache-Control": REVALIDATE})
    return {"message": "Birthday Tracker API", "docs": "/docs"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
