"""Tests for Pydantic data models."""

import pytest
from pydantic import ValidationError

from app.models import (
    Birthday,
    BirthdayCreate,
    BirthdayUpdate,
    EmailSettings,
    Token,
    TokenData,
    User,
    UserCreate,
    UserResponse,
)


class TestBirthdayModel:
    def test_create_birthday_minimal(self):
        b = Birthday(name="Alice", month=3, day=15)
        assert b.name == "Alice"
        assert b.month == 3
        assert b.day == 15
        assert b.birth_year is None
        assert b.note is None
        assert b.contact_type == "Friend"
        assert b.id is None

    def test_create_birthday_full(self):
        b = Birthday(
            id="abc-123",
            name="Bob",
            birth_year=1990,
            month=12,
            day=25,
            note="Colleague",
            contact_type="Business",
        )
        assert b.id == "abc-123"
        assert b.birth_year == 1990
        assert b.note == "Colleague"
        assert b.contact_type == "Business"

    def test_birthday_month_boundaries(self):
        Birthday(name="Jan", month=1, day=1)
        Birthday(name="Dec", month=12, day=31)

    def test_birthday_invalid_month_zero(self):
        with pytest.raises(ValidationError):
            Birthday(name="X", month=0, day=1)

    def test_birthday_invalid_month_13(self):
        with pytest.raises(ValidationError):
            Birthday(name="X", month=13, day=1)

    def test_birthday_invalid_day_zero(self):
        with pytest.raises(ValidationError):
            Birthday(name="X", month=1, day=0)

    def test_birthday_invalid_day_32(self):
        with pytest.raises(ValidationError):
            Birthday(name="X", month=1, day=32)

    def test_birthday_day_can_be_none(self):
        """Month-only birthdays (day unknown) are allowed."""
        b = Birthday(name="X", month=6)
        assert b.day is None

    def test_birthday_negative_month(self):
        with pytest.raises(ValidationError):
            Birthday(name="X", month=-1, day=1)


class TestBirthdayCreateModel:
    def test_day_is_required(self):
        """BirthdayCreate requires a day (unlike Birthday)."""
        with pytest.raises(ValidationError):
            BirthdayCreate(name="X", month=6)

    def test_valid_create(self):
        bc = BirthdayCreate(name="Alice", month=3, day=15)
        assert bc.name == "Alice"
        assert bc.day == 15


class TestBirthdayUpdateModel:
    def test_all_fields_optional(self):
        """Update model should accept empty payload (no fields)."""
        bu = BirthdayUpdate()
        assert bu.name is None
        assert bu.month is None
        assert bu.day is None

    def test_partial_update(self):
        bu = BirthdayUpdate(name="Updated Name")
        assert bu.name == "Updated Name"
        assert bu.month is None

    def test_invalid_month_in_update(self):
        with pytest.raises(ValidationError):
            BirthdayUpdate(month=13)


class TestUserModels:
    def test_user_defaults(self):
        u = User(username="test", hashed_password="hash")
        assert u.disabled is False
        assert u.is_admin is False

    def test_user_create(self):
        uc = UserCreate(username="new", password="secret")
        assert uc.is_admin is False

    def test_user_response_no_password(self):
        ur = UserResponse(username="test", disabled=False, is_admin=True)
        assert not hasattr(ur, "hashed_password")
        assert not hasattr(ur, "password")


class TestEmailSettings:
    def test_defaults(self):
        es = EmailSettings()
        assert es.enabled is False
        assert es.smtp_port == 587
        assert es.reminder_time == "09:00"
        assert es.recipients == []
        assert es.ai_enabled is False
        assert es.openai_api_key == ""
        assert es.test_mode is False

    def test_custom_settings(self):
        es = EmailSettings(
            enabled=True,
            smtp_server="smtp.example.com",
            smtp_port=465,
            recipients=["a@example.com", "b@example.com"],
            ai_enabled=True,
            openai_api_key="sk-test",
        )
        assert es.smtp_port == 465
        assert len(es.recipients) == 2
        assert es.ai_enabled is True


class TestTokenModels:
    def test_token(self):
        t = Token(access_token="abc", token_type="bearer")
        assert t.access_token == "abc"

    def test_token_data_default(self):
        td = TokenData()
        assert td.username is None
