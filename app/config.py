"""Application configuration."""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Data storage
DATA_DIR = Path(os.getenv("BIRTHDAYS_DATA_DIR", BASE_DIR / "data"))
BIRTHDAYS_FILE = DATA_DIR / "birthdays.json"
USERS_FILE = DATA_DIR / "users.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

# Security
SECRET_KEY = os.getenv(
    "BIRTHDAYS_SECRET_KEY", "change-this-in-production-use-a-real-secret-key"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Default admin credentials (change in production!)
DEFAULT_ADMIN_USERNAME = os.getenv("BIRTHDAYS_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("BIRTHDAYS_ADMIN_PASSWORD", "changeme")

# Swagger UI, ReDoc and the OpenAPI schema. Off by default: the endpoints they
# describe all require a token, but on a public deployment they advertise the
# entire API surface to anyone who asks, for no benefit to the people actually
# using the app. Set BIRTHDAYS_ENABLE_DOCS=true when working against the API.
ENABLE_DOCS = os.getenv("BIRTHDAYS_ENABLE_DOCS", "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
