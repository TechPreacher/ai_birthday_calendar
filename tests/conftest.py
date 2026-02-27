"""Shared test fixtures."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.models import User
from app.storage import UserStorage, BirthdayStorage, SettingsStorage


# The secret key used in tests — must match what we patch into auth.
TEST_SECRET_KEY = "test-secret-key"


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path):
    """Redirect all storage to a temporary directory for every test.

    Patches storage instances everywhere they are referenced so that all
    modules (auth, routes, scheduler) use the tmp-backed stores.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create fresh storage instances backed by tmp files
    tmp_user_storage = UserStorage(data_dir / "users.json")
    tmp_birthday_storage = BirthdayStorage(data_dir / "birthdays.json")
    tmp_settings_storage = SettingsStorage(data_dir / "settings.json")

    # Every module that imports a storage singleton or SECRET_KEY needs patching.
    patches = [
        # Storage singletons
        patch("app.storage.user_storage", tmp_user_storage),
        patch("app.storage.birthday_storage", tmp_birthday_storage),
        patch("app.storage.settings_storage", tmp_settings_storage),
        patch("app.auth.user_storage", tmp_user_storage),
        patch("app.routes.auth.user_storage", tmp_user_storage),
        patch("app.routes.birthdays.birthday_storage", tmp_birthday_storage),
        patch("app.routes.settings.settings_storage", tmp_settings_storage),
        patch("app.scheduler.birthday_storage", tmp_birthday_storage),
        patch("app.scheduler.settings_storage", tmp_settings_storage),
        # SECRET_KEY — used for JWT signing in auth.py
        patch("app.auth.SECRET_KEY", TEST_SECRET_KEY),
        # Default admin credentials
        patch("app.auth.DEFAULT_ADMIN_USERNAME", "admin"),
        patch("app.auth.DEFAULT_ADMIN_PASSWORD", "testpass123"),
    ]

    for p in patches:
        p.start()

    yield tmp_path

    for p in patches:
        p.stop()


@pytest.fixture
def user_storage():
    """Return the (patched) user storage for the current test."""
    from app.storage import user_storage

    return user_storage


@pytest.fixture
def birthday_storage():
    """Return the (patched) birthday storage for the current test."""
    from app.storage import birthday_storage

    return birthday_storage


@pytest.fixture
def settings_storage():
    """Return the (patched) settings storage for the current test."""
    from app.storage import settings_storage

    return settings_storage


@pytest.fixture
def admin_user(user_storage):
    """Create and return an admin user."""
    from app.auth import get_password_hash

    admin = User(
        username="admin",
        hashed_password=get_password_hash("testpass123"),
        disabled=False,
        is_admin=True,
    )
    user_storage.create(admin)
    return admin


@pytest.fixture
def regular_user(user_storage):
    """Create and return a non-admin user."""
    from app.auth import get_password_hash

    user = User(
        username="regular",
        hashed_password=get_password_hash("userpass123"),
        disabled=False,
        is_admin=False,
    )
    user_storage.create(user)
    return user


@pytest.fixture
def client(isolated_data_dir, admin_user):
    """Provide a FastAPI TestClient with scheduler disabled."""
    with (
        patch("app.main.start_scheduler"),
        patch("app.main.stop_scheduler"),
        patch("app.main.migrate_birthdays_add_ids"),
        patch("app.main.ensure_default_admin"),
    ):
        from app.main import app

        with TestClient(app) as c:
            yield c


@pytest.fixture
def admin_token(client):
    """Get a valid admin JWT token."""
    response = client.post(
        "/api/auth/token",
        data={"username": "admin", "password": "testpass123"},
    )
    return response.json()["access_token"]


@pytest.fixture
def admin_headers(admin_token):
    """Auth headers for admin user."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def regular_token(client, regular_user):
    """Get a valid non-admin JWT token."""
    response = client.post(
        "/api/auth/token",
        data={"username": "regular", "password": "userpass123"},
    )
    return response.json()["access_token"]


@pytest.fixture
def regular_headers(regular_token):
    """Auth headers for non-admin user."""
    return {"Authorization": f"Bearer {regular_token}"}
