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


class TestOverLongPasswordVerification:
    """bcrypt raises above 72 bytes; verify must not let that become a 500."""

    def test_verify_returns_false_instead_of_raising(self):
        hashed = get_password_hash("correct-horse")
        assert verify_password("x" * 200, hashed) is False

    def test_a_password_at_the_limit_still_verifies(self):
        password = "a" * 72
        assert verify_password(password, get_password_hash(password)) is True

    def test_login_with_an_over_long_password_is_401_not_500(self, client):
        """/api/auth/token is public, so anyone could reach this error path."""
        response = client.post(
            "/api/auth/token",
            data={"username": "admin", "password": "x" * 200},
        )
        assert response.status_code == 401


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


class TestTokenExpiryIsTimezoneAware:
    """create_access_token used datetime.utcnow(), deprecated in 3.12."""

    def test_expiry_is_roughly_the_configured_lifetime(self):
        from datetime import datetime, timezone
        from jose import jwt
        from app.config import ACCESS_TOKEN_EXPIRE_MINUTES
        from tests.conftest import TEST_SECRET_KEY

        token = create_access_token({"sub": "admin"})
        exp = jwt.decode(token, TEST_SECRET_KEY, algorithms=["HS256"])["exp"]

        expected = datetime.now(timezone.utc).timestamp() + ACCESS_TOKEN_EXPIRE_MINUTES * 60
        # A naive/aware mix-up would be out by whole hours; allow a minute.
        assert abs(exp - expected) < 60

    def test_an_expired_token_is_rejected(self, client):
        """The sign of the offset must still be interpreted correctly."""
        from datetime import timedelta

        token = create_access_token({"sub": "admin"}, expires_delta=timedelta(minutes=-5))
        response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401

    def test_a_fresh_token_is_accepted(self, client):
        from datetime import timedelta

        token = create_access_token({"sub": "admin"}, expires_delta=timedelta(minutes=5))
        response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
