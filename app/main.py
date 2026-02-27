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

# Static files
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


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
        return FileResponse(index_path)
    return {"message": "Birthday Tracker API", "docs": "/docs"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
