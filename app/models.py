"""Data models."""

from typing import Annotated, Optional
from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    StringConstraints,
    model_validator,
)

from .dates import month_day_error

# A person's name, as accepted from a client. Whitespace is stripped first, so
# a name of only spaces is rejected rather than stored -- it would otherwise
# render as an empty, unclickable row in the calendar.
BirthdayName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]

# bcrypt hashes at most 72 bytes of a password and ignores the rest. bcrypt 5.x
# raises rather than truncating, which surfaced as a 500 from the API; 4.x
# truncated silently, which is worse -- two different passwords sharing their
# first 72 bytes verify against the same hash. So the limit is enforced here,
# before anything reaches the hashing call.
#
# The limit is in BYTES, not characters: an accented letter is two bytes in
# UTF-8 and an emoji is four, so a password well under 72 characters can still
# exceed it.
BCRYPT_MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LENGTH = 6


def _check_password_bytes(value: str) -> str:
    encoded_length = len(value.encode("utf-8"))
    if encoded_length > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password is too long: {encoded_length} bytes, maximum is "
            f"{BCRYPT_MAX_PASSWORD_BYTES}. That is about 72 ordinary "
            "characters; accented letters count as two and emoji as four."
        )
    return value


Password = Annotated[
    str,
    StringConstraints(min_length=MIN_PASSWORD_LENGTH),
    AfterValidator(_check_password_bytes),
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
    password: Password
    is_admin: bool = False


class PasswordChange(BaseModel):
    """Password change request.

    This endpoint previously took a bare dict and checked the length by hand,
    so the minimum was enforced here but not at user creation. Sharing the
    Password type keeps the two consistent.
    """

    password: Password

    # Required when changing your own password, ignored when an admin changes
    # someone else's. Deliberately a plain str rather than the Password type:
    # it is an existing password being checked, and applying today's policy to
    # it could reject an account whose password predates the rules.
    current_password: Optional[str] = None


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

    @model_validator(mode="after")
    def _month_and_day_form_a_real_date(self):
        # ge/le check the two fields separately, which lets February 31 and
        # April 31 through. Such an entry can never match a real day, so it
        # would never produce a reminder.
        error = month_day_error(self.month, self.day)
        if error:
            raise ValueError(error)
        return self


class BirthdayUpdate(BaseModel):
    """Birthday update model."""

    name: Optional[BirthdayName] = None
    birth_year: Optional[int] = None
    month: Optional[int] = Field(None, ge=1, le=12)
    day: Optional[int] = Field(None, ge=1, le=31)
    note: Optional[str] = None
    contact_type: Optional[str] = None  # "Friend" or "Business"

    @model_validator(mode="after")
    def _month_and_day_form_a_real_date(self):
        # Only checks what this request supplies. A partial update that changes
        # just one of the pair is validated against the merged result in the
        # route, since copy(update=...) does not re-run validation.
        error = month_day_error(self.month, self.day)
        if error:
            raise ValueError(error)
        return self


# Sent in place of a stored secret so the browser never receives the SMTP
# password or the OpenAI key. Saving it back unchanged means "keep what is
# stored"; any other value replaces the secret, and an empty string clears it.
#
# Deliberately not a run of asterisks or bullets, which someone could
# plausibly have chosen as an actual password.
SECRET_PLACEHOLDER = "__stored_secret_unchanged__"

# Fields never returned to a client in the clear.
SECRET_SETTING_FIELDS = ("smtp_password", "openai_api_key")


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
