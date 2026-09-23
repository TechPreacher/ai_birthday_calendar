"""Data models."""

from typing import Annotated, Optional
from pydantic import BaseModel, Field, StringConstraints

# A person's name, as accepted from a client. Whitespace is stripped first, so
# a name of only spaces is rejected rather than stored -- it would otherwise
# render as an empty, unclickable row in the calendar.
BirthdayName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


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

    # Constrained so a username is always safe as a single URL path segment.
    # /api/auth/users/{username} cannot match a name containing "/", and an
    # empty name cannot be addressed at all -- either produces an account that
    # is impossible to delete through the API or the UI.
    #
    # Only the creation model is constrained, never User: existing accounts are
    # read back from users.json unchanged, whatever they are named.
    username: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
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

    # Constrained on input only, so existing entries still load unchanged.
    name: BirthdayName
    birth_year: Optional[int] = None
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)
    note: Optional[str] = None
    contact_type: str = "Friend"  # "Friend" or "Business"


class BirthdayUpdate(BaseModel):
    """Birthday update model."""

    name: Optional[BirthdayName] = None
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
