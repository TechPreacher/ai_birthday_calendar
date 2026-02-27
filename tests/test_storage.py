"""Tests for JSON storage layer."""

import pytest

from app.models import Birthday, EmailSettings, User


class TestUserStorage:
    def test_create_and_get_user(self, user_storage):
        user = User(username="alice", hashed_password="hash123", is_admin=False)
        user_storage.create(user)

        fetched = user_storage.get_by_username("alice")
        assert fetched is not None
        assert fetched.username == "alice"
        assert fetched.hashed_password == "hash123"

    def test_get_nonexistent_user(self, user_storage):
        assert user_storage.get_by_username("nobody") is None

    def test_exists(self, user_storage):
        user = User(username="bob", hashed_password="hash")
        user_storage.create(user)
        assert user_storage.exists("bob") is True
        assert user_storage.exists("ghost") is False

    def test_duplicate_username_raises(self, user_storage):
        user = User(username="alice", hashed_password="hash")
        user_storage.create(user)
        with pytest.raises(ValueError, match="already exists"):
            user_storage.create(user)

    def test_get_all_users(self, user_storage):
        user_storage.create(User(username="a", hashed_password="h"))
        user_storage.create(User(username="b", hashed_password="h"))
        assert len(user_storage.get_all()) == 2

    def test_update_user(self, user_storage):
        user = User(username="alice", hashed_password="old_hash")
        user_storage.create(user)

        user.hashed_password = "new_hash"
        result = user_storage.update("alice", user)
        assert result.hashed_password == "new_hash"

        fetched = user_storage.get_by_username("alice")
        assert fetched.hashed_password == "new_hash"

    def test_update_nonexistent_user(self, user_storage):
        user = User(username="ghost", hashed_password="h")
        assert user_storage.update("ghost", user) is None

    def test_delete_user(self, user_storage):
        user = User(username="alice", hashed_password="h")
        user_storage.create(user)
        assert user_storage.delete("alice") is True
        assert user_storage.exists("alice") is False

    def test_delete_nonexistent_user(self, user_storage):
        assert user_storage.delete("nobody") is False

    def test_empty_file_returns_empty_list(self, user_storage):
        assert user_storage.get_all() == []


class TestBirthdayStorage:
    def test_create_birthday_generates_id(self, birthday_storage):
        b = Birthday(name="Alice", month=3, day=15)
        created = birthday_storage.create(b)
        assert created.id is not None
        assert len(created.id) > 0

    def test_create_birthday_preserves_given_id(self, birthday_storage):
        b = Birthday(id="custom-id", name="Bob", month=6, day=1)
        created = birthday_storage.create(b)
        assert created.id == "custom-id"

    def test_get_by_id(self, birthday_storage):
        created = birthday_storage.create(Birthday(name="Alice", month=3, day=15))
        fetched = birthday_storage.get_by_id(created.id)
        assert fetched is not None
        assert fetched.name == "Alice"

    def test_get_by_id_nonexistent(self, birthday_storage):
        assert birthday_storage.get_by_id("nonexistent") is None

    def test_get_all_empty(self, birthday_storage):
        assert birthday_storage.get_all() == []

    def test_get_all_multiple(self, birthday_storage):
        birthday_storage.create(Birthday(name="A", month=1, day=1))
        birthday_storage.create(Birthday(name="B", month=2, day=2))
        birthday_storage.create(Birthday(name="C", month=3, day=3))
        assert len(birthday_storage.get_all()) == 3

    def test_update_birthday(self, birthday_storage):
        created = birthday_storage.create(
            Birthday(name="Alice", month=3, day=15, note="Old note")
        )
        updated = Birthday(name="Alice Smith", month=3, day=15, note="New note")
        result = birthday_storage.update(created.id, updated)
        assert result.name == "Alice Smith"
        assert result.note == "New note"
        assert result.id == created.id  # ID preserved

    def test_update_nonexistent(self, birthday_storage):
        b = Birthday(name="Ghost", month=1, day=1)
        assert birthday_storage.update("nonexistent", b) is None

    def test_delete_birthday(self, birthday_storage):
        created = birthday_storage.create(Birthday(name="Alice", month=3, day=15))
        assert birthday_storage.delete(created.id) is True
        assert birthday_storage.get_by_id(created.id) is None

    def test_delete_nonexistent(self, birthday_storage):
        assert birthday_storage.delete("nonexistent") is False

    def test_save_all(self, birthday_storage):
        birthdays = [
            Birthday(id="1", name="A", month=1, day=1),
            Birthday(id="2", name="B", month=2, day=2),
        ]
        birthday_storage.save_all(birthdays)
        assert len(birthday_storage.get_all()) == 2

    def test_get_all_assigns_ids_to_legacy_entries(self, birthday_storage):
        """Birthdays without IDs (pre-migration) should get IDs assigned on read."""
        # Write raw data without IDs
        data = {"birthdays": [{"name": "Legacy", "month": 5, "day": 10}]}
        birthday_storage._write(data)

        result = birthday_storage.get_all()
        assert len(result) == 1
        assert result[0].id is not None
        assert result[0].name == "Legacy"

    def test_birthday_with_all_fields(self, birthday_storage):
        b = Birthday(
            name="Full Entry",
            birth_year=1985,
            month=7,
            day=20,
            note="Best friend",
            contact_type="Business",
        )
        created = birthday_storage.create(b)
        fetched = birthday_storage.get_by_id(created.id)
        assert fetched.birth_year == 1985
        assert fetched.contact_type == "Business"
        assert fetched.note == "Best friend"


class TestSettingsStorage:
    def test_default_settings(self, settings_storage):
        settings = settings_storage.get_email_settings()
        assert settings.enabled is False
        assert settings.smtp_port == 587

    def test_save_and_load_settings(self, settings_storage):
        settings = EmailSettings(
            enabled=True,
            smtp_server="smtp.example.com",
            smtp_port=465,
            smtp_username="user@example.com",
            smtp_password="secret",
            from_email="noreply@example.com",
            recipients=["admin@example.com"],
            reminder_time="08:00",
            ai_enabled=True,
            openai_api_key="sk-test",
        )
        settings_storage.save_email_settings(settings)

        loaded = settings_storage.get_email_settings()
        assert loaded.enabled is True
        assert loaded.smtp_server == "smtp.example.com"
        assert loaded.smtp_port == 465
        assert loaded.recipients == ["admin@example.com"]
        assert loaded.ai_enabled is True
        assert loaded.openai_api_key == "sk-test"

    def test_overwrite_settings(self, settings_storage):
        settings_storage.save_email_settings(EmailSettings(enabled=True))
        settings_storage.save_email_settings(EmailSettings(enabled=False))
        assert settings_storage.get_email_settings().enabled is False


class TestMigration:
    def test_migrate_adds_ids(self, birthday_storage):
        """The migration function should add IDs to entries that lack them."""
        from app.storage import migrate_birthdays_add_ids

        # Write raw data without IDs
        data = {
            "birthdays": [
                {"name": "A", "month": 1, "day": 1},
                {"name": "B", "month": 2, "day": 2, "id": "existing-id"},
                {"name": "C", "month": 3, "day": 3, "id": ""},
            ]
        }
        birthday_storage._write(data)

        migrate_birthdays_add_ids()

        all_birthdays = birthday_storage.get_all()
        assert len(all_birthdays) == 3
        for b in all_birthdays:
            assert b.id is not None and b.id != ""

        # Existing ID should be preserved
        b_entry = next(b for b in all_birthdays if b.name == "B")
        assert b_entry.id == "existing-id"
