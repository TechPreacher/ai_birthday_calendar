"""Data models."""

from typing import Optional
from pydantic import BaseModel, Field


class Token(BaseModel):
    """OAuth2 token."""

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token payload data."""

    username: Optional[str] = None


class User(BaseModel):
    """User model."""

    username: str
    hashed_password: str
    disabled: bool = False
    is_admin: bool = False


class UserCreate(BaseModel):
    """User creation model."""

    username: str
    password: str
    is_admin: bool = False


class UserResponse(BaseModel):
    """User response (without password)."""

    username: str
    disabled: bool
    is_admin: bool


class Birthday(BaseModel):
    """Birthday model."""

    id: Optional[str] = None
    name: str
    birth_year: Optional[int] = None
    month: int = Field(ge=1, le=12)
    day: Optional[int] = Field(None, ge=1, le=31)
    note: Optional[str] = None
    contact_type: str = "Friend"  # "Friend" or "Business"


class BirthdayCreate(BaseModel):
    """Birthday creation model."""

    name: str
    birth_year: Optional[int] = None
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)
    note: Optional[str] = None
    contact_type: str = "Friend"  # "Friend" or "Business"


class BirthdayUpdate(BaseModel):
    """Birthday update model."""

    name: Optional[str] = None
    birth_year: Optional[int] = None
    month: Optional[int] = Field(None, ge=1, le=12)
    day: Optional[int] = Field(None, ge=1, le=31)
    note: Optional[str] = None
    contact_type: Optional[str] = None  # "Friend" or "Business"


class EmailSettings(BaseModel):
    """Email notification settings."""

    enabled: bool = False
    smtp_server: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    from_email: str = ""
    recipients: list[str] = Field(default_factory=list)
    reminder_time: str = "09:00"  # HH:MM format
    test_mode: bool = False  # If true, sends test emails to admin only
    ai_enabled: bool = False  # Enable AI-generated gift ideas and messages
    openai_api_key: str = ""  # OpenAI API key for AI features
