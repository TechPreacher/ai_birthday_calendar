"""Authentication utilities."""

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from .config import (
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_ADMIN_PASSWORD,
)
from .models import BCRYPT_MAX_PASSWORD_BYTES, User, TokenData
from .storage import user_storage

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    bcrypt raises for anything over 72 bytes rather than truncating. Such a
    password can never be correct, because passwords are capped at 72 bytes
    when they are set, so treat it as a mismatch. Letting that exception
    escape turned the login endpoint into a 500 for anyone submitting a long
    string -- unauthenticated, on a publicly reachable route.
    """
    encoded = plain_password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(encoded, hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    # datetime.utcnow() is deprecated in Python 3.12: it returns a naive
    # datetime that merely happens to hold UTC, which is easy to compare
    # against a local time by mistake. An aware value says what it is.
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate a user."""
    user = user_storage.get_by_username(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Get the current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = user_storage.get_by_username(token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get the current active (non-disabled) user."""
    if current_user.disabled:
        # 401, not 400. A token issued before the account was disabled is no
        # longer usable, which is an authentication failure -- and the client
        # only clears its stored token and returns to the login screen on a
        # 401. A 400 left it looping on a session that could never succeed.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account has been disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def ensure_default_admin():
    """Ensure the default admin user exists."""
    if not user_storage.exists(DEFAULT_ADMIN_USERNAME):
        # This value comes from the environment and bypasses the API's
        # validation, so check it here rather than letting bcrypt raise an
        # opaque ValueError during startup.
        if len(DEFAULT_ADMIN_PASSWORD.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
            raise RuntimeError(
                f"BIRTHDAYS_ADMIN_PASSWORD is longer than "
                f"{BCRYPT_MAX_PASSWORD_BYTES} bytes, which bcrypt cannot hash. "
                "Shorten it and restart."
            )

        admin = User(
            username=DEFAULT_ADMIN_USERNAME,
            hashed_password=get_password_hash(DEFAULT_ADMIN_PASSWORD),
            disabled=False,
            is_admin=True,
        )
        user_storage.create(admin)
