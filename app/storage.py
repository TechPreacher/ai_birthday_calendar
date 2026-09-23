"""Data storage layer."""

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import List, Optional
from threading import Lock

from .models import User, Birthday, EmailSettings
from .config import BIRTHDAYS_FILE, USERS_FILE, SETTINGS_FILE

# These files hold password hashes, the SMTP password and the OpenAI API key,
# so they are kept readable by the owner only. Set explicitly on every write:
# an atomic replace installs a brand-new inode, which would otherwise take its
# permissions from the process umask.
DATA_FILE_MODE = 0o600


class JSONStorage:
    """Base JSON file storage."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.lock = Lock()
        self._ensure_file()

    def _ensure_file(self):
        """Ensure the JSON file and directory exist."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._write({})

    def _read(self) -> dict:
        """Read data from JSON file."""
        with self.lock:
            with open(self.file_path, "r") as f:
                return json.load(f)

    def _write(self, data: dict):
        """Write data to the JSON file atomically.

        Writing in place would truncate the file before the new contents are
        written, so a crash mid-write (OOM kill, reboot, container stop) would
        leave a truncated file and lose every record. Instead the data goes to
        a temporary file in the same directory, is flushed to disk, and is then
        moved into place with os.replace() -- an atomic rename on POSIX. A
        reader therefore sees either the whole old file or the whole new one,
        never a partial write.
        """
        with self.lock:
            directory = self.file_path.parent
            fd, tmp_path = tempfile.mkstemp(
                dir=directory, prefix=f".{self.file_path.name}.", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())

                os.chmod(tmp_path, DATA_FILE_MODE)
                os.replace(tmp_path, self.file_path)

                # Flush the rename itself, so the swap survives a power loss
                # and not just a process crash.
                dir_fd = os.open(directory, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except BaseException:
                # Never leave a stray temp file behind on failure.
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise


class UserStorage(JSONStorage):
    """User storage."""

    def get_all(self) -> List[User]:
        """Get all users."""
        data = self._read()
        return [User(**user) for user in data.get("users", [])]

    def get_by_username(self, username: str) -> Optional[User]:
        """Get a user by username."""
        users = self.get_all()
        return next((u for u in users if u.username == username), None)

    def exists(self, username: str) -> bool:
        """Check if a user exists."""
        return self.get_by_username(username) is not None

    def create(self, user: User) -> User:
        """Create a new user."""
        data = self._read()
        if "users" not in data:
            data["users"] = []

        # Check if username already exists
        if any(u.get("username") == user.username for u in data["users"]):
            raise ValueError(f"User {user.username} already exists")

        data["users"].append(user.model_dump())
        self._write(data)
        return user

    def update(self, username: str, user: User) -> Optional[User]:
        """Update a user."""
        data = self._read()
        users = data.get("users", [])

        for i, u in enumerate(users):
            if u.get("username") == username:
                users[i] = user.model_dump()
                self._write(data)
                return user

        return None

    def delete(self, username: str) -> bool:
        """Delete a user."""
        data = self._read()
        users = data.get("users", [])

        initial_len = len(users)
        data["users"] = [u for u in users if u.get("username") != username]

        if len(data["users"]) < initial_len:
            self._write(data)
            return True
        return False


class BirthdayStorage(JSONStorage):
    """Birthday storage."""

    def get_all(self) -> List[Birthday]:
        """Get all birthdays."""
        data = self._read()
        birthdays = []
        for b in data.get("birthdays", []):
            # Ensure all birthdays have IDs
            if "id" not in b or not b["id"]:
                b["id"] = str(uuid.uuid4())
            birthdays.append(Birthday(**b))
        return birthdays

    def get_by_id(self, birthday_id: str) -> Optional[Birthday]:
        """Get a birthday by ID."""
        birthdays = self.get_all()
        return next((b for b in birthdays if b.id == birthday_id), None)

    def create(self, birthday: Birthday) -> Birthday:
        """Create a new birthday."""
        data = self._read()
        if "birthdays" not in data:
            data["birthdays"] = []

        # Generate ID if not provided
        if not birthday.id:
            birthday.id = str(uuid.uuid4())

        data["birthdays"].append(birthday.model_dump())
        self._write(data)
        return birthday

    def update(self, birthday_id: str, birthday: Birthday) -> Optional[Birthday]:
        """Update a birthday."""
        data = self._read()
        birthdays = data.get("birthdays", [])

        for i, b in enumerate(birthdays):
            if b.get("id") == birthday_id:
                birthday.id = birthday_id  # Preserve ID
                birthdays[i] = birthday.model_dump()
                self._write(data)
                return birthday

        return None

    def delete(self, birthday_id: str) -> bool:
        """Delete a birthday."""
        data = self._read()
        birthdays = data.get("birthdays", [])

        initial_len = len(birthdays)
        data["birthdays"] = [b for b in birthdays if b.get("id") != birthday_id]

        if len(data["birthdays"]) < initial_len:
            self._write(data)
            return True
        return False

    def save_all(self, birthdays: List[Birthday]):
        """Save all birthdays (used for migration/bulk update)."""
        data = {"birthdays": [b.model_dump() for b in birthdays]}
        self._write(data)


class SettingsStorage(JSONStorage):
    """Settings storage."""

    def get_email_settings(self) -> EmailSettings:
        """Get email settings."""
        data = self._read()
        if "email" in data:
            return EmailSettings(**data["email"])
        return EmailSettings()

    def save_email_settings(self, settings: EmailSettings):
        """Save email settings."""
        data = self._read()
        data["email"] = settings.model_dump()
        self._write(data)


# Initialize storage instances
user_storage = UserStorage(USERS_FILE)
birthday_storage = BirthdayStorage(BIRTHDAYS_FILE)
settings_storage = SettingsStorage(SETTINGS_FILE)


def migrate_birthdays_add_ids():
    """Migrate existing birthdays to add IDs if missing."""
    # Read raw data
    data = birthday_storage._read()
    birthdays_data = data.get("birthdays", [])
    modified = False

    for birthday_dict in birthdays_data:
        if "id" not in birthday_dict or not birthday_dict["id"]:
            birthday_dict["id"] = str(uuid.uuid4())
            modified = True

    if modified:
        data["birthdays"] = birthdays_data
        birthday_storage._write(data)
        print(f"Migrated {len(birthdays_data)} birthdays with IDs")
