"""Tests for the birthday reminder scheduler."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


from app.models import Birthday, EmailSettings
from app.scheduler import (
    calculate_age,
    check_and_send_reminders,
    generate_ai_suggestions,
)


class TestCalculateAge:
    def test_basic_age(self):
        assert calculate_age(1990, 2026) == 36

    def test_birth_year_equals_current(self):
        assert calculate_age(2026, 2026) == 0

    def test_future_birth_year_negative(self):
        """Edge case: birth year in the future gives negative age."""
        assert calculate_age(2030, 2026) == -4

    def test_very_old(self):
        assert calculate_age(1900, 2026) == 126


class TestGenerateAISuggestions:
    def _mock_response(self, content):
        """Build a mock OpenAI response."""
        choice = MagicMock()
        choice.message.content = content
        response = MagicMock()
        response.choices = [choice]
        return response

    @patch("app.scheduler.OpenAI", create=True)
    def test_parse_well_formed_response(self, mock_openai_cls):
        client = MagicMock()
        mock_openai_cls.return_value = client
        client.chat.completions.create.return_value = self._mock_response(
            "MESSAGE: Happy birthday to Alice! Wishing you a wonderful day.\n\n"
            "GIFTS:\n"
            "1. A nice book\n"
            "2. A scarf\n"
            "3. Concert tickets\n"
            "4. Cooking class\n"
            "5. Photo album\n"
        )

        # Need to patch the import inside the function
        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai_cls)}):
            result = generate_ai_suggestions(
                "Alice", age=30, note="Loves reading", api_key="sk-test"
            )

        assert result is not None
        assert "Happy birthday" in result["message"]
        assert len(result["gifts"]) == 5
        assert "A nice book" in result["gifts"]

    @patch("app.scheduler.OpenAI", create=True)
    def test_parse_with_dash_list(self, mock_openai_cls):
        client = MagicMock()
        mock_openai_cls.return_value = client
        client.chat.completions.create.return_value = self._mock_response(
            "MESSAGE: Happy birthday!\n\nGIFTS:\n- Gift one\n- Gift two\n- Gift three\n"
        )

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai_cls)}):
            result = generate_ai_suggestions("Bob", api_key="sk-test")

        assert result is not None
        assert len(result["gifts"]) == 3

    @patch("app.scheduler.OpenAI", create=True)
    def test_more_than_5_gifts_truncated(self, mock_openai_cls):
        client = MagicMock()
        mock_openai_cls.return_value = client
        gifts = "\n".join(f"{i}. Gift {i}" for i in range(1, 9))
        client.chat.completions.create.return_value = self._mock_response(
            f"MESSAGE: Happy birthday!\n\nGIFTS:\n{gifts}\n"
        )

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai_cls)}):
            result = generate_ai_suggestions("Test", api_key="sk-test")

        assert len(result["gifts"]) <= 5

    def test_api_failure_returns_none(self):
        """When OpenAI import or call fails, should return None gracefully."""
        with patch.dict("sys.modules", {"openai": None}):
            result = generate_ai_suggestions("Alice", api_key="bad-key")
        assert result is None

    @patch("app.scheduler.OpenAI", create=True)
    def test_no_age_no_note(self, mock_openai_cls):
        """Should work with minimal info (name only)."""
        client = MagicMock()
        mock_openai_cls.return_value = client
        client.chat.completions.create.return_value = self._mock_response(
            "MESSAGE: Happy birthday!\n\nGIFTS:\n1. A gift\n"
        )

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai_cls)}):
            result = generate_ai_suggestions("Alice", api_key="sk-test")

        assert result is not None


class TestCheckAndSendReminders:
    def _setup_birthday_tomorrow(self, birthday_storage, settings_storage, **kwargs):
        """Helper to set up a birthday for tomorrow and enable email."""
        tomorrow = datetime.now() + timedelta(days=1)
        bday = Birthday(
            id="test-id",
            name=kwargs.get("name", "Test Person"),
            birth_year=kwargs.get("birth_year", 1990),
            month=tomorrow.month,
            day=tomorrow.day,
            note=kwargs.get("note", None),
            contact_type=kwargs.get("contact_type", "Friend"),
        )
        birthday_storage.create(bday)

        settings = EmailSettings(
            enabled=True,
            smtp_server="smtp.example.com",
            smtp_port=587,
            smtp_username="user@example.com",
            smtp_password="pass",
            from_email="from@example.com",
            recipients=["recipient@example.com"],
            test_mode=kwargs.get("test_mode", True),
            ai_enabled=kwargs.get("ai_enabled", False),
        )
        settings_storage.save_email_settings(settings)
        return bday

    def test_no_reminders_when_disabled(self, birthday_storage, settings_storage):
        """Should not send emails when notifications are disabled."""
        self._setup_birthday_tomorrow(birthday_storage, settings_storage)
        settings_storage.save_email_settings(EmailSettings(enabled=False))

        with patch("app.scheduler.send_email") as mock_send:
            check_and_send_reminders()
            mock_send.assert_not_called()

    def test_no_reminders_when_no_recipients(self, birthday_storage, settings_storage):
        """Should not send when there are no recipients."""
        self._setup_birthday_tomorrow(birthday_storage, settings_storage)
        settings = settings_storage.get_email_settings()
        settings.recipients = []
        settings_storage.save_email_settings(settings)

        with patch("app.scheduler.send_email") as mock_send:
            check_and_send_reminders()
            mock_send.assert_not_called()

    def test_no_birthdays_tomorrow(self, birthday_storage, settings_storage):
        """No email when there are no birthdays tomorrow."""
        # Create a birthday far from tomorrow
        birthday_storage.create(Birthday(id="x", name="Far Away", month=1, day=1))
        settings_storage.save_email_settings(
            EmailSettings(
                enabled=True,
                recipients=["a@example.com"],
                smtp_server="smtp.example.com",
                from_email="from@example.com",
            )
        )

        # If tomorrow is Jan 1, this test still works since we just need
        # no match on the other entry
        tomorrow = datetime.now() + timedelta(days=1)
        if tomorrow.month == 1 and tomorrow.day == 1:
            # Edge case: if tomorrow IS Jan 1, use a different month
            birthday_storage._write(
                {"birthdays": [{"id": "x", "name": "Far", "month": 6, "day": 15}]}
            )

        with patch("app.scheduler.send_email") as mock_send:
            check_and_send_reminders()
            mock_send.assert_not_called()

    def test_test_mode_logs_instead_of_sending(
        self, birthday_storage, settings_storage
    ):
        """Test mode should log but not call send_email."""
        self._setup_birthday_tomorrow(
            birthday_storage, settings_storage, test_mode=True
        )

        with patch("app.scheduler.send_email") as mock_send:
            check_and_send_reminders()
            mock_send.assert_not_called()

    def test_sends_email_in_normal_mode(self, birthday_storage, settings_storage):
        """Normal mode should call send_email."""
        self._setup_birthday_tomorrow(
            birthday_storage, settings_storage, test_mode=False
        )

        with patch("app.scheduler.send_email") as mock_send:
            check_and_send_reminders()
            mock_send.assert_called_once()
            args = mock_send.call_args
            assert "Birthday Reminder" in args[0][0]  # subject
            assert "Test Person" in args[0][1]  # body

    def test_email_includes_age_when_birth_year_set(
        self, birthday_storage, settings_storage
    ):
        """Email body should include age info when birth year is known."""
        self._setup_birthday_tomorrow(
            birthday_storage, settings_storage, birth_year=1990, test_mode=False
        )

        with patch("app.scheduler.send_email") as mock_send:
            check_and_send_reminders()
            body = mock_send.call_args[0][1]
            assert "turning" in body

    def test_email_without_birth_year(self, birthday_storage, settings_storage):
        """Email should work without birth year (no age displayed)."""
        tomorrow = datetime.now() + timedelta(days=1)
        birthday_storage.create(
            Birthday(
                id="no-year", name="Ageless", month=tomorrow.month, day=tomorrow.day
            )
        )
        settings_storage.save_email_settings(
            EmailSettings(
                enabled=True,
                recipients=["r@example.com"],
                smtp_server="smtp.example.com",
                from_email="f@example.com",
                test_mode=False,
            )
        )

        with patch("app.scheduler.send_email") as mock_send:
            check_and_send_reminders()
            body = mock_send.call_args[0][1]
            assert "Ageless" in body
            assert "turning" not in body

    def test_email_includes_note(self, birthday_storage, settings_storage):
        """Notes should appear in the email body."""
        self._setup_birthday_tomorrow(
            birthday_storage, settings_storage, note="Best friend", test_mode=False
        )

        with patch("app.scheduler.send_email") as mock_send:
            check_and_send_reminders()
            body = mock_send.call_args[0][1]
            assert "Best friend" in body

    def test_skips_birthdays_with_null_day(self, birthday_storage, settings_storage):
        """Birthdays with day=None should not trigger reminders."""
        tomorrow = datetime.now() + timedelta(days=1)
        # Write raw data with null day
        data = {
            "birthdays": [
                {
                    "id": "null-day",
                    "name": "NoDay",
                    "month": tomorrow.month,
                    "day": None,
                }
            ]
        }
        birthday_storage._write(data)

        settings_storage.save_email_settings(
            EmailSettings(
                enabled=True,
                recipients=["r@example.com"],
                smtp_server="smtp.example.com",
                from_email="f@example.com",
            )
        )

        with patch("app.scheduler.send_email") as mock_send:
            check_and_send_reminders()
            mock_send.assert_not_called()

    def test_multiple_birthdays_same_day(self, birthday_storage, settings_storage):
        """Multiple birthdays on the same day should all appear in one email."""
        tomorrow = datetime.now() + timedelta(days=1)
        for name in ["Alice", "Bob", "Charlie"]:
            birthday_storage.create(
                Birthday(name=name, month=tomorrow.month, day=tomorrow.day)
            )

        settings_storage.save_email_settings(
            EmailSettings(
                enabled=True,
                recipients=["r@example.com"],
                smtp_server="smtp.example.com",
                from_email="f@example.com",
                test_mode=False,
            )
        )

        with patch("app.scheduler.send_email") as mock_send:
            check_and_send_reminders()
            mock_send.assert_called_once()
            subject = mock_send.call_args[0][0]
            body = mock_send.call_args[0][1]
            assert "3 birthday(s)" in subject
            assert "Alice" in body
            assert "Bob" in body
            assert "Charlie" in body


class TestSchedulerConfig:
    def test_start_scheduler_with_valid_time(self, settings_storage):
        settings_storage.save_email_settings(EmailSettings(reminder_time="14:30"))

        with patch("app.scheduler.BackgroundScheduler") as MockScheduler:
            import app.scheduler as sched

            sched.scheduler = None  # Reset global state
            mock_instance = MagicMock()
            MockScheduler.return_value = mock_instance

            sched.start_scheduler()

            mock_instance.add_job.assert_called_once()
            mock_instance.start.assert_called_once()

            # Clean up
            sched.scheduler = None

    def test_start_scheduler_with_invalid_time_falls_back(self, settings_storage):
        settings_storage.save_email_settings(EmailSettings(reminder_time="invalid"))

        with patch("app.scheduler.BackgroundScheduler") as MockScheduler:
            import app.scheduler as sched

            sched.scheduler = None
            mock_instance = MagicMock()
            MockScheduler.return_value = mock_instance

            sched.start_scheduler()

            # Should still start (falls back to 09:00)
            mock_instance.start.assert_called_once()
            sched.scheduler = None

    def test_start_scheduler_ignores_if_already_running(self, settings_storage):
        import app.scheduler as sched

        sched.scheduler = MagicMock()  # Pretend it's running

        with patch("app.scheduler.BackgroundScheduler") as MockScheduler:
            sched.start_scheduler()
            MockScheduler.assert_not_called()

        sched.scheduler = None

    def test_stop_scheduler(self):
        import app.scheduler as sched

        mock_sched = MagicMock()
        sched.scheduler = mock_sched

        sched.stop_scheduler()

        mock_sched.shutdown.assert_called_once()
        assert sched.scheduler is None

    def test_stop_scheduler_when_not_running(self):
        import app.scheduler as sched

        sched.scheduler = None
        sched.stop_scheduler()  # Should not raise

    def test_reschedule(self, settings_storage):
        import app.scheduler as sched

        sched.scheduler = MagicMock()

        with patch("app.scheduler.BackgroundScheduler") as MockScheduler:
            mock_instance = MagicMock()
            MockScheduler.return_value = mock_instance

            sched.reschedule_reminders()

            # Should have stopped old and started new
            mock_instance.start.assert_called_once()

        sched.scheduler = None
