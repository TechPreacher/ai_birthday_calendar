"""Tests for authentication utilities."""

from datetime import timedelta

from jose import jwt

from app.auth import (
    authenticate_user,
    create_access_token,
    ensure_default_admin,
    get_password_hash,
    verify_password,
)
from app.models import User


class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = get_password_hash("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_wrong_password(self):
        hashed = get_password_hash("correct")
        assert verify_password("wrong", hashed) is False

    def test_hash_is_not_plaintext(self):
        hashed = get_password_hash("secret")
        assert hashed != "secret"

    def test_different_hashes_for_same_password(self):
        """bcrypt uses random salts, so hashes should differ."""
        h1 = get_password_hash("same")
        h2 = get_password_hash("same")
        assert h1 != h2

    def test_empty_password(self):
        hashed = get_password_hash("")
        assert verify_password("", hashed) is True
        assert verify_password("notempty", hashed) is False

    def test_unicode_password(self):
        hashed = get_password_hash("p@$$wörd!")
        assert verify_password("p@$$wörd!", hashed) is True


class TestJWT:
    def test_create_and_decode_token(self):
        token = create_access_token(data={"sub": "testuser"})
        payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        assert payload["sub"] == "testuser"
        assert "exp" in payload

    def test_custom_expiry(self):
        token = create_access_token(
            data={"sub": "user"}, expires_delta=timedelta(minutes=5)
        )
        payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        assert payload["sub"] == "user"

    def test_token_contains_expiry(self):
        token = create_access_token(data={"sub": "user"})
        payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        assert "exp" in payload


class TestAuthentication:
    def test_authenticate_valid_user(self, user_storage):
        hashed = get_password_hash("secret123")
        user_storage.create(User(username="alice", hashed_password=hashed))

        result = authenticate_user("alice", "secret123")
        assert result is not None
        assert result.username == "alice"

    def test_authenticate_wrong_password(self, user_storage):
        hashed = get_password_hash("correct")
        user_storage.create(User(username="alice", hashed_password=hashed))

        assert authenticate_user("alice", "wrong") is None

    def test_authenticate_nonexistent_user(self, user_storage):
        assert authenticate_user("nobody", "password") is None


class TestEnsureDefaultAdmin:
    def test_creates_admin_when_missing(self, user_storage):
        ensure_default_admin()
        admin = user_storage.get_by_username("admin")
        assert admin is not None
        assert admin.is_admin is True
        assert admin.disabled is False

    def test_does_not_duplicate_admin(self, user_storage):
        ensure_default_admin()
        ensure_default_admin()  # Call twice
        users = user_storage.get_all()
        admin_count = sum(1 for u in users if u.username == "admin")
        assert admin_count == 1
