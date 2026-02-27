"""Tests for API endpoints."""


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
        assert response.status_code == 400
        assert "at least 6" in response.json()["detail"]

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
