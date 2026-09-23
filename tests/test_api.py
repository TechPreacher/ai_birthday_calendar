"""Tests for API endpoints."""

import pytest

from app.models import SECRET_PLACEHOLDER


class TestHealthAndRoot:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root_returns_html_or_json(self, client):
        response = client.get("/")
        # Root serves either static HTML or a JSON fallback
        assert response.status_code == 200


class TestAuthAPI:
    def test_login_success(self, client):
        response = client.post(
            "/api/auth/token",
            data={"username": "admin", "password": "testpass123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        response = client.post(
            "/api/auth/token",
            data={"username": "admin", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        response = client.post(
            "/api/auth/token",
            data={"username": "nobody", "password": "password"},
        )
        assert response.status_code == 401

    def test_get_current_user(self, client, admin_headers):
        response = client.get("/api/auth/me", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        assert data["is_admin"] is True
        assert "hashed_password" not in data

    def test_unauthenticated_request(self, client):
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_invalid_token(self, client):
        response = client.get(
            "/api/auth/me", headers={"Authorization": "Bearer invalidtoken"}
        )
        assert response.status_code == 401


class TestUserManagement:
    def test_list_users_as_admin(self, client, admin_headers):
        response = client.get("/api/auth/users", headers=admin_headers)
        assert response.status_code == 200
        users = response.json()
        assert any(u["username"] == "admin" for u in users)

    def test_list_users_as_non_admin(self, client, regular_headers):
        response = client.get("/api/auth/users", headers=regular_headers)
        assert response.status_code == 403

    def test_create_user(self, client, admin_headers):
        response = client.post(
            "/api/auth/users",
            json={"username": "newuser", "password": "pass123456", "is_admin": False},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["username"] == "newuser"

    def test_create_duplicate_user(self, client, admin_headers):
        client.post(
            "/api/auth/users",
            json={"username": "dupe", "password": "pass123456"},
            headers=admin_headers,
        )
        response = client.post(
            "/api/auth/users",
            json={"username": "dupe", "password": "pass123456"},
            headers=admin_headers,
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_create_user_as_non_admin(self, client, regular_headers):
        response = client.post(
            "/api/auth/users",
            json={"username": "hacker", "password": "pass123456"},
            headers=regular_headers,
        )
        assert response.status_code == 403

    @pytest.mark.parametrize(
        "username",
        [
            "a/b",  # a slash makes DELETE /users/{username} unroutable
            "",  # empty name cannot be addressed as a path segment at all
            "a b",  # space
            "a?b",  # query separator
            "a#b",  # fragment separator
            "../admin",  # path traversal attempt
            "x" * 65,  # over the length limit
        ],
    )
    def test_create_user_rejects_unroutable_username(
        self, client, admin_headers, username
    ):
        """Usernames must be safe as a single URL path segment.

        A name containing "/" (or an empty one) produced an account that could
        never be deleted through the API, because no route could match it.
        """
        response = client.post(
            "/api/auth/users",
            json={"username": username, "password": "pass123456"},
            headers=admin_headers,
        )
        assert response.status_code == 422

        # And it must not have been created as a side effect.
        listed = client.get("/api/auth/users", headers=admin_headers).json()
        assert username not in [u["username"] for u in listed]

    def test_created_user_is_always_deletable(self, client, admin_headers):
        """Whatever a valid username looks like, it round-trips through a URL."""
        for username in ["plain", "with.dot", "with-dash", "with_underscore", "MiXed123"]:
            created = client.post(
                "/api/auth/users",
                json={"username": username, "password": "pass123456"},
                headers=admin_headers,
            )
            assert created.status_code == 200, username

            deleted = client.delete(
                f"/api/auth/users/{username}", headers=admin_headers
            )
            assert deleted.status_code == 200, username

    def test_change_password(self, client, admin_headers):
        # Create a user first
        client.post(
            "/api/auth/users",
            json={"username": "target", "password": "oldpass123"},
            headers=admin_headers,
        )

        response = client.put(
            "/api/auth/users/target/password",
            json={"password": "newpass123"},
            headers=admin_headers,
        )
        assert response.status_code == 200

        # Verify new password works
        login = client.post(
            "/api/auth/token",
            data={"username": "target", "password": "newpass123"},
        )
        assert login.status_code == 200

    def test_change_password_too_short(self, client, admin_headers):
        client.post(
            "/api/auth/users",
            json={"username": "target", "password": "oldpass123"},
            headers=admin_headers,
        )
        response = client.put(
            "/api/auth/users/target/password",
            json={"password": "short"},
            headers=admin_headers,
        )
        # The endpoint validates through the shared Password type now, so the
        # minimum is reported as a 422 rather than a hand-rolled 400.
        assert response.status_code == 422

    def test_create_user_too_short_password(self, client, admin_headers):
        """The minimum used to be enforced on change but not on creation."""
        response = client.post(
            "/api/auth/users",
            json={"username": "shortpw", "password": "1"},
            headers=admin_headers,
        )
        assert response.status_code == 422

    @pytest.mark.parametrize(
        "password,expected,why",
        [
            ("a" * 72, 200, "exactly at bcrypt's limit"),
            ("a" * 73, 422, "one byte over"),
            ("é" * 36, 200, "36 two-byte chars = 72 bytes"),
            ("é" * 37, 422, "37 two-byte chars = 74 bytes"),
            ("\U0001f600" * 18, 200, "18 four-byte emoji = 72 bytes"),
            ("\U0001f600" * 19, 422, "19 four-byte emoji = 76 bytes"),
        ],
    )
    def test_password_length_limit_is_counted_in_bytes(
        self, client, admin_headers, password, expected, why
    ):
        """bcrypt's limit is 72 BYTES, not characters.

        Over-long passwords previously reached bcrypt and raised, which the API
        returned as a 500. Note the emoji cases are far below 72 characters yet
        still over the byte limit.
        """
        response = client.post(
            "/api/auth/users",
            json={"username": f"u{len(password)}{expected}", "password": password},
            headers=admin_headers,
        )
        assert response.status_code == expected, why

    def test_over_long_password_is_rejected_not_a_server_error(
        self, client, admin_headers
    ):
        """Regression: this used to be an unhandled ValueError from bcrypt."""
        response = client.post(
            "/api/auth/users",
            json={"username": "longpw", "password": "x" * 200},
            headers=admin_headers,
        )
        assert response.status_code != 500
        assert response.status_code == 422
        # The message must name the real limit so it is actionable.
        assert "72" in str(response.json()["detail"])

    def test_password_at_limit_can_actually_log_in(self, client, admin_headers):
        """A password accepted at the boundary must still round-trip."""
        password = "b" * 72
        client.post(
            "/api/auth/users",
            json={"username": "atlimit", "password": password},
            headers=admin_headers,
        )
        login = client.post(
            "/api/auth/token",
            data={"username": "atlimit", "password": password},
        )
        assert login.status_code == 200

    def test_non_admin_can_change_own_password(
        self, client, admin_headers, regular_headers
    ):
        """The gap: a non-admin could never rotate their own credentials."""
        response = client.put(
            "/api/auth/users/regular/password",
            json={"password": "brandnew123", "current_password": "userpass123"},
            headers=regular_headers,
        )
        assert response.status_code == 200

        # The new password works...
        assert (
            client.post(
                "/api/auth/token",
                data={"username": "regular", "password": "brandnew123"},
            ).status_code
            == 200
        )
        # ...and the old one no longer does.
        assert (
            client.post(
                "/api/auth/token",
                data={"username": "regular", "password": "userpass123"},
            ).status_code
            == 401
        )

    def test_own_password_change_requires_the_current_one(
        self, client, regular_headers
    ):
        """A stolen token must not be enough to take the account over."""
        response = client.put(
            "/api/auth/users/regular/password",
            json={"password": "brandnew123"},
            headers=regular_headers,
        )
        assert response.status_code == 400
        assert "current password" in response.json()["detail"].lower()

        # The password is unchanged.
        assert (
            client.post(
                "/api/auth/token",
                data={"username": "regular", "password": "userpass123"},
            ).status_code
            == 200
        )

    def test_own_password_change_rejects_a_wrong_current_password(
        self, client, regular_headers
    ):
        response = client.put(
            "/api/auth/users/regular/password",
            json={"password": "brandnew123", "current_password": "notmypassword"},
            headers=regular_headers,
        )
        # 400, not 401: a 401 would log the user out of the session they hold.
        assert response.status_code == 400

    def test_wrong_current_password_does_not_end_the_session(
        self, client, regular_headers
    ):
        """Mistyping must leave the caller still authenticated."""
        client.put(
            "/api/auth/users/regular/password",
            json={"password": "brandnew123", "current_password": "wrong"},
            headers=regular_headers,
        )
        assert client.get("/api/auth/me", headers=regular_headers).status_code == 200

    def test_non_admin_cannot_change_someone_elses_password(
        self, client, admin_headers, regular_headers
    ):
        client.post(
            "/api/auth/users",
            json={"username": "victim", "password": "victimpass"},
            headers=admin_headers,
        )
        response = client.put(
            "/api/auth/users/victim/password",
            json={"password": "hijacked123", "current_password": "userpass123"},
            headers=regular_headers,
        )
        assert response.status_code == 403

        # The victim's password still works.
        assert (
            client.post(
                "/api/auth/token",
                data={"username": "victim", "password": "victimpass"},
            ).status_code
            == 200
        )

    def test_non_admin_gets_403_not_404_for_an_unknown_user(
        self, client, regular_headers
    ):
        """Permission is checked before existence, so no user enumeration."""
        response = client.put(
            "/api/auth/users/ghost/password",
            json={"password": "whatever123", "current_password": "userpass123"},
            headers=regular_headers,
        )
        assert response.status_code == 403

    def test_admin_changing_someone_else_needs_no_current_password(
        self, client, admin_headers
    ):
        """Unchanged behaviour: an admin does not know the other password."""
        client.post(
            "/api/auth/users",
            json={"username": "other", "password": "otherpass"},
            headers=admin_headers,
        )
        response = client.put(
            "/api/auth/users/other/password",
            json={"password": "resetbyadmin"},
            headers=admin_headers,
        )
        assert response.status_code == 200

    def test_admin_changing_own_password_needs_the_current_one(
        self, client, admin_headers
    ):
        """Self-change is self-change; the admin session is the best target."""
        response = client.put(
            "/api/auth/users/admin/password",
            json={"password": "newadminpass"},
            headers=admin_headers,
        )
        assert response.status_code == 400

        ok = client.put(
            "/api/auth/users/admin/password",
            json={"password": "newadminpass", "current_password": "testpass123"},
            headers=admin_headers,
        )
        assert ok.status_code == 200

    def test_self_change_still_enforces_password_rules(
        self, client, regular_headers
    ):
        response = client.put(
            "/api/auth/users/regular/password",
            json={"password": "x" * 200, "current_password": "userpass123"},
            headers=regular_headers,
        )
        assert response.status_code == 422

    def test_change_password_nonexistent_user(self, client, admin_headers):
        response = client.put(
            "/api/auth/users/ghost/password",
            json={"password": "newpass123"},
            headers=admin_headers,
        )
        assert response.status_code == 404

    def test_delete_user(self, client, admin_headers):
        client.post(
            "/api/auth/users",
            json={"username": "deleteme", "password": "pass123456"},
            headers=admin_headers,
        )
        response = client.delete("/api/auth/users/deleteme", headers=admin_headers)
        assert response.status_code == 200

    def test_delete_self_forbidden(self, client, admin_headers):
        response = client.delete("/api/auth/users/admin", headers=admin_headers)
        assert response.status_code == 400
        assert "Cannot delete your own" in response.json()["detail"]

    def test_delete_nonexistent_user(self, client, admin_headers):
        response = client.delete("/api/auth/users/ghost", headers=admin_headers)
        assert response.status_code == 404


class TestBirthdayAPI:
    def test_list_birthdays_empty(self, client, admin_headers):
        response = client.get("/api/birthdays", headers=admin_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_birthday(self, client, admin_headers):
        response = client.post(
            "/api/birthdays",
            json={"name": "Alice", "month": 3, "day": 15},
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Alice"
        assert data["month"] == 3
        assert data["day"] == 15
        assert data["id"] is not None
        assert data["contact_type"] == "Friend"

    @pytest.mark.parametrize(
        "month,day", [(2, 30), (2, 31), (4, 31), (6, 31), (9, 31), (11, 31)]
    )
    def test_create_birthday_rejects_impossible_date(
        self, client, admin_headers, month, day
    ):
        """month and day used to be validated independently, so Feb 31 passed.

        Such an entry can never match a real day, so it would never produce a
        reminder.
        """
        response = client.post(
            "/api/birthdays",
            json={"name": "Nobody", "month": month, "day": day},
            headers=admin_headers,
        )
        assert response.status_code == 422
        assert client.get("/api/birthdays", headers=admin_headers).json() == []

    def test_create_birthday_accepts_feb_29(self, client, admin_headers):
        """Leap-day birthdays are real and must be storable."""
        response = client.post(
            "/api/birthdays",
            json={"name": "Leapling", "month": 2, "day": 29},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["day"] == 29

    def test_partial_update_cannot_create_an_impossible_date(
        self, client, admin_headers
    ):
        """copy(update=...) skips validation, so the merged pair is checked.

        Changing only the day of a February entry to 31 must not slip through.
        """
        created = client.post(
            "/api/birthdays",
            json={"name": "Alice", "month": 2, "day": 10},
            headers=admin_headers,
        ).json()

        response = client.put(
            f"/api/birthdays/{created['id']}",
            json={"day": 31},
            headers=admin_headers,
        )
        assert response.status_code == 422

        unchanged = client.get(
            f"/api/birthdays/{created['id']}", headers=admin_headers
        ).json()
        assert unchanged["day"] == 10

    @pytest.mark.parametrize("name", ["", "   "])
    def test_create_birthday_rejects_blank_name(self, client, admin_headers, name):
        """A blank name renders as an empty, unclickable row in the calendar."""
        response = client.post(
            "/api/birthdays",
            json={"name": name, "month": 3, "day": 15},
            headers=admin_headers,
        )
        assert response.status_code == 422
        assert client.get("/api/birthdays", headers=admin_headers).json() == []

    def test_update_birthday_rejects_blank_name(self, client, admin_headers):
        created = client.post(
            "/api/birthdays",
            json={"name": "Alice", "month": 3, "day": 15},
            headers=admin_headers,
        ).json()

        response = client.put(
            f"/api/birthdays/{created['id']}",
            json={"name": ""},
            headers=admin_headers,
        )
        assert response.status_code == 422

        # The original name must survive the rejected update.
        unchanged = client.get(
            f"/api/birthdays/{created['id']}", headers=admin_headers
        ).json()
        assert unchanged["name"] == "Alice"

    def test_create_birthday_full(self, client, admin_headers):
        response = client.post(
            "/api/birthdays",
            json={
                "name": "Bob",
                "birth_year": 1985,
                "month": 12,
                "day": 25,
                "note": "Colleague",
                "contact_type": "Business",
            },
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["birth_year"] == 1985
        assert data["note"] == "Colleague"
        assert data["contact_type"] == "Business"

    def test_create_birthday_invalid_month(self, client, admin_headers):
        response = client.post(
            "/api/birthdays",
            json={"name": "Bad", "month": 13, "day": 1},
            headers=admin_headers,
        )
        assert response.status_code == 422

    def test_create_birthday_invalid_day(self, client, admin_headers):
        response = client.post(
            "/api/birthdays",
            json={"name": "Bad", "month": 1, "day": 32},
            headers=admin_headers,
        )
        assert response.status_code == 422

    def test_create_birthday_unauthenticated(self, client):
        response = client.post(
            "/api/birthdays",
            json={"name": "Alice", "month": 3, "day": 15},
        )
        assert response.status_code == 401

    def test_get_birthday_by_id(self, client, admin_headers):
        create_resp = client.post(
            "/api/birthdays",
            json={"name": "Alice", "month": 3, "day": 15},
            headers=admin_headers,
        )
        birthday_id = create_resp.json()["id"]

        response = client.get(f"/api/birthdays/{birthday_id}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["name"] == "Alice"

    def test_get_birthday_not_found(self, client, admin_headers):
        response = client.get("/api/birthdays/nonexistent", headers=admin_headers)
        assert response.status_code == 404

    def test_update_birthday(self, client, admin_headers):
        create_resp = client.post(
            "/api/birthdays",
            json={"name": "Alice", "month": 3, "day": 15},
            headers=admin_headers,
        )
        birthday_id = create_resp.json()["id"]

        response = client.put(
            f"/api/birthdays/{birthday_id}",
            json={"name": "Alice Smith", "note": "Updated"},
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Alice Smith"
        assert data["note"] == "Updated"
        assert data["month"] == 3  # Unchanged fields preserved
        assert data["day"] == 15

    def test_update_birthday_not_found(self, client, admin_headers):
        response = client.put(
            "/api/birthdays/nonexistent",
            json={"name": "Ghost"},
            headers=admin_headers,
        )
        assert response.status_code == 404

    def test_delete_birthday(self, client, admin_headers):
        create_resp = client.post(
            "/api/birthdays",
            json={"name": "ToDelete", "month": 1, "day": 1},
            headers=admin_headers,
        )
        birthday_id = create_resp.json()["id"]

        response = client.delete(f"/api/birthdays/{birthday_id}", headers=admin_headers)
        assert response.status_code == 200

        # Verify it's gone
        get_resp = client.get(f"/api/birthdays/{birthday_id}", headers=admin_headers)
        assert get_resp.status_code == 404

    def test_delete_birthday_not_found(self, client, admin_headers):
        response = client.delete("/api/birthdays/nonexistent", headers=admin_headers)
        assert response.status_code == 404

    def test_non_admin_can_crud_birthdays(self, client, regular_headers):
        """Regular users should be able to manage birthdays too."""
        create_resp = client.post(
            "/api/birthdays",
            json={"name": "UserBday", "month": 5, "day": 20},
            headers=regular_headers,
        )
        assert create_resp.status_code == 200

        birthday_id = create_resp.json()["id"]

        list_resp = client.get("/api/birthdays", headers=regular_headers)
        assert list_resp.status_code == 200

        update_resp = client.put(
            f"/api/birthdays/{birthday_id}",
            json={"note": "From regular user"},
            headers=regular_headers,
        )
        assert update_resp.status_code == 200

        delete_resp = client.delete(
            f"/api/birthdays/{birthday_id}", headers=regular_headers
        )
        assert delete_resp.status_code == 200


class TestSettingsAPI:
    def test_get_settings_as_admin(self, client, admin_headers):
        response = client.get("/api/settings/email", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "smtp_server" in data

    def test_get_settings_as_non_admin(self, client, regular_headers):
        response = client.get("/api/settings/email", headers=regular_headers)
        assert response.status_code == 403

    def test_update_settings(self, client, admin_headers):
        from unittest.mock import patch

        with patch("app.routes.settings.reschedule_reminders"):
            response = client.put(
                "/api/settings/email",
                json={
                    "enabled": True,
                    "smtp_server": "smtp.example.com",
                    "smtp_port": 587,
                    "smtp_username": "user@example.com",
                    "smtp_password": "pass",
                    "from_email": "noreply@example.com",
                    "recipients": ["admin@example.com"],
                    "reminder_time": "08:00",
                },
                headers=admin_headers,
            )
        assert response.status_code == 200
        assert response.json()["enabled"] is True
        assert response.json()["smtp_server"] == "smtp.example.com"

    def test_update_settings_as_non_admin(self, client, regular_headers):
        response = client.put(
            "/api/settings/email",
            json={"enabled": True},
            headers=regular_headers,
        )
        assert response.status_code == 403

    def test_test_email_disabled(self, client, admin_headers):
        """Test email should fail when notifications are disabled."""
        response = client.post("/api/settings/email/test", headers=admin_headers)
        assert response.status_code == 400
        assert "disabled" in response.json()["detail"]

    def test_test_email_no_recipients(self, client, admin_headers, settings_storage):
        """Test email should fail with no recipients."""
        from app.models import EmailSettings
        from unittest.mock import patch

        settings_storage.save_email_settings(EmailSettings(enabled=True, recipients=[]))

        with patch("app.routes.settings.reschedule_reminders"):
            response = client.post("/api/settings/email/test", headers=admin_headers)
        assert response.status_code == 400
        assert "recipients" in response.json()["detail"].lower()

    def test_test_ai_email_not_enabled(self, client, admin_headers, settings_storage):
        """AI test email should fail when AI is disabled."""
        from app.models import EmailSettings

        settings_storage.save_email_settings(
            EmailSettings(
                enabled=True,
                recipients=["a@example.com"],
                ai_enabled=False,
            )
        )
        response = client.post("/api/settings/email/test-ai", headers=admin_headers)
        assert response.status_code == 400

    def test_test_ai_email_no_api_key(self, client, admin_headers, settings_storage):
        """AI test email should fail without an API key."""
        from app.models import EmailSettings

        settings_storage.save_email_settings(
            EmailSettings(
                enabled=True,
                recipients=["a@example.com"],
                ai_enabled=True,
                openai_api_key="",
            )
        )
        response = client.post("/api/settings/email/test-ai", headers=admin_headers)
        assert response.status_code == 400

    def test_test_ai_no_birthdays(self, client, admin_headers, settings_storage):
        """AI test should fail when there are no birthdays."""
        from app.models import EmailSettings

        settings_storage.save_email_settings(
            EmailSettings(
                enabled=True,
                recipients=["a@example.com"],
                ai_enabled=True,
                openai_api_key="sk-test",
            )
        )
        response = client.post("/api/settings/email/test-ai", headers=admin_headers)
        assert response.status_code == 400
        assert "No birthdays" in response.json()["detail"]


class TestStaticCaching:
    """A deploy must not leave browsers running yesterday's JavaScript."""

    def test_index_asks_browsers_to_revalidate(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers.get("cache-control") == "no-cache"

    def test_static_assets_ask_browsers_to_revalidate(self, client):
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        assert response.headers.get("cache-control") == "no-cache"

    def test_static_assets_still_carry_an_etag(self, client):
        """no-cache means revalidate, so an unchanged file must 304."""
        first = client.get("/static/js/app.js")
        etag = first.headers.get("etag")
        assert etag

        second = client.get("/static/js/app.js", headers={"If-None-Match": etag})
        assert second.status_code == 304


class TestDisabledAccounts:
    """A disabled account used to log in fine and then fail every request."""

    def _disable(self, user_storage, username):
        user = user_storage.get_by_username(username)
        user.disabled = True
        user_storage.update(username, user)

    def test_disabled_user_cannot_log_in(self, client, user_storage, regular_user):
        self._disable(user_storage, "regular")

        response = client.post(
            "/api/auth/token",
            data={"username": "regular", "password": "userpass123"},
        )
        assert response.status_code == 403
        assert "disabled" in response.json()["detail"].lower()

    def test_disabled_user_gets_no_token(self, client, user_storage, regular_user):
        """The real bug: a valid token was issued, then nothing worked."""
        self._disable(user_storage, "regular")

        response = client.post(
            "/api/auth/token",
            data={"username": "regular", "password": "userpass123"},
        )
        assert "access_token" not in response.json()

    def test_wrong_password_on_a_disabled_account_stays_generic(
        self, client, user_storage, regular_user
    ):
        """Disabled status must not leak to someone without the password."""
        self._disable(user_storage, "regular")

        response = client.post(
            "/api/auth/token",
            data={"username": "regular", "password": "not-the-password"},
        )
        assert response.status_code == 401
        assert "disabled" not in response.json()["detail"].lower()

    def test_existing_token_stops_working_when_disabled(
        self, client, user_storage, regular_headers
    ):
        """A session already in progress must end, as a 401 so the client
        clears its token rather than looping on an unusable session."""
        assert client.get("/api/auth/me", headers=regular_headers).status_code == 200

        self._disable(user_storage, "regular")

        response = client.get("/api/auth/me", headers=regular_headers)
        assert response.status_code == 401
        assert response.headers.get("www-authenticate") == "Bearer"

    def test_disabled_user_cannot_reach_data_endpoints(
        self, client, user_storage, regular_headers
    ):
        self._disable(user_storage, "regular")
        assert client.get("/api/birthdays", headers=regular_headers).status_code == 401

    def test_active_users_are_unaffected(self, client, regular_headers):
        assert client.get("/api/auth/me", headers=regular_headers).status_code == 200


class TestSettingsSecretsAreMasked:
    """The SMTP password and OpenAI key must never reach the browser."""

    FAKE_SMTP = "not-a-real-smtp-password"
    FAKE_KEY = "not-a-real-openai-key-0123456789"

    def _store(self, client, admin_headers, **overrides):
        payload = {
            "enabled": True,
            "smtp_server": "smtp.example.com",
            "smtp_username": "user@example.com",
            "smtp_password": self.FAKE_SMTP,
            "from_email": "from@example.com",
            "recipients": ["a@example.com"],
            "ai_enabled": True,
            "openai_api_key": self.FAKE_KEY,
        }
        payload.update(overrides)
        return client.put("/api/settings/email", json=payload, headers=admin_headers)

    def test_get_never_returns_the_real_secrets(self, client, admin_headers):
        self._store(client, admin_headers)

        body = client.get("/api/settings/email", headers=admin_headers).json()

        assert self.FAKE_SMTP not in str(body)
        assert self.FAKE_KEY not in str(body)
        assert body["smtp_password"] == SECRET_PLACEHOLDER
        assert body["openai_api_key"] == SECRET_PLACEHOLDER

    def test_put_response_is_masked_too(self, client, admin_headers):
        body = self._store(client, admin_headers).json()
        assert self.FAKE_SMTP not in str(body)
        assert self.FAKE_KEY not in str(body)

    def test_the_real_secrets_are_still_stored(self, client, admin_headers, settings_storage):
        """Masking is presentation only -- the scheduler still needs them."""
        self._store(client, admin_headers)

        stored = settings_storage.get_email_settings()
        assert stored.smtp_password == self.FAKE_SMTP
        assert stored.openai_api_key == self.FAKE_KEY

    def test_saving_the_form_untouched_keeps_the_secrets(
        self, client, admin_headers, settings_storage
    ):
        """The round trip that would otherwise destroy them."""
        self._store(client, admin_headers)

        returned = client.get("/api/settings/email", headers=admin_headers).json()
        client.put("/api/settings/email", json=returned, headers=admin_headers)

        stored = settings_storage.get_email_settings()
        assert stored.smtp_password == self.FAKE_SMTP
        assert stored.openai_api_key == self.FAKE_KEY

    def test_a_new_value_replaces_the_secret(
        self, client, admin_headers, settings_storage
    ):
        self._store(client, admin_headers)
        self._store(client, admin_headers, smtp_password="a-different-password")

        assert settings_storage.get_email_settings().smtp_password == "a-different-password"

    def test_an_empty_value_clears_the_secret(
        self, client, admin_headers, settings_storage
    ):
        """Clearing must still be possible, and distinguishable from unchanged."""
        self._store(client, admin_headers)
        self._store(client, admin_headers, smtp_password="")

        assert settings_storage.get_email_settings().smtp_password == ""

    def test_an_unset_secret_reads_back_empty_not_masked(self, client, admin_headers):
        """So the screen can show whether a secret is configured at all."""
        self._store(client, admin_headers, smtp_password="", openai_api_key="")

        body = client.get("/api/settings/email", headers=admin_headers).json()
        assert body["smtp_password"] == ""
        assert body["openai_api_key"] == ""

    def test_non_admin_still_refused(self, client, regular_headers):
        assert client.get("/api/settings/email", headers=regular_headers).status_code == 403


class TestDocsDisabledByDefault:
    """The API surface should not be advertised on a public deployment."""

    def test_swagger_ui_is_not_served(self, client):
        assert client.get("/docs").status_code == 404

    def test_redoc_is_not_served(self, client):
        assert client.get("/redoc").status_code == 404

    def test_openapi_schema_is_not_served(self, client):
        """Disabling the UIs alone would leave the schema readable."""
        assert client.get("/openapi.json").status_code == 404

    def test_the_app_itself_still_works(self, client, admin_headers):
        assert client.get("/health").status_code == 200
        assert client.get("/api/birthdays", headers=admin_headers).status_code == 200

    @pytest.mark.parametrize(
        "value,expected",
        [("true", True), ("1", True), ("yes", True), ("on", True), ("TRUE", True),
         ("", False), ("false", False), ("0", False), ("no", False), ("maybe", False)],
    )
    def test_the_flag_parses_sensibly(self, monkeypatch, value, expected):
        monkeypatch.setenv("BIRTHDAYS_ENABLE_DOCS", value)
        import importlib
        from app import config
        importlib.reload(config)
        try:
            assert config.ENABLE_DOCS is expected
        finally:
            monkeypatch.delenv("BIRTHDAYS_ENABLE_DOCS", raising=False)
            importlib.reload(config)
