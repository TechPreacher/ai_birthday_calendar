"""Authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from ..models import Token, User, UserCreate, UserResponse
from ..auth import (
    authenticate_user,
    create_access_token,
    get_current_active_user,
    get_password_hash,
)
from ..storage import user_storage

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login and get access token."""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.username})
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """Get current user information."""
    return UserResponse(
        username=current_user.username,
        disabled=current_user.disabled,
        is_admin=current_user.is_admin,
    )


@router.get("/users", response_model=list[UserResponse])
async def list_users(current_user: User = Depends(get_current_active_user)):
    """List all users (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    users = user_storage.get_all()
    return [
        UserResponse(username=u.username, disabled=u.disabled, is_admin=u.is_admin)
        for u in users
    ]


@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate, current_user: User = Depends(get_current_active_user)
):
    """Create a new user (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    if user_storage.exists(user_data.username):
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=user_data.username,
        hashed_password=get_password_hash(user_data.password),
        disabled=False,
        is_admin=user_data.is_admin,
    )

    created_user = user_storage.create(user)
    return UserResponse(
        username=created_user.username,
        disabled=created_user.disabled,
        is_admin=created_user.is_admin,
    )


@router.put("/users/{username}/password")
async def change_user_password(
    username: str,
    password_data: dict,
    current_user: User = Depends(get_current_active_user),
):
    """Change a user's password (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    new_password = password_data.get("password")
    if not new_password or len(new_password) < 6:
        raise HTTPException(
            status_code=400, detail="Password must be at least 6 characters"
        )

    user = user_storage.get_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update password
    user.hashed_password = get_password_hash(new_password)
    user_storage.update(username, user)

    return {"message": f"Password updated for {username}"}


@router.delete("/users/{username}")
async def delete_user(
    username: str, current_user: User = Depends(get_current_active_user)
):
    """Delete a user (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    if username == current_user.username:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    if not user_storage.delete(username):
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": f"User {username} deleted"}
