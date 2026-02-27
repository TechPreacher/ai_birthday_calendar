"""Birthday reminder scheduler."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
import re

from .storage import birthday_storage, settings_storage

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None


def calculate_age(birth_year: int, current_year: int) -> int:
    """Calculate age."""
    return current_year - birth_year


def send_email(subject: str, body: str, recipients: list, settings):
    """Send an email via SMTP."""
    try:
        msg = MIMEMultipart()
        msg["From"] = settings.from_email
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "html"))

        # Strip all whitespace from password (Gmail app passwords have spaces/non-breaking spaces)
        import re

        password = re.sub(r"\s", "", settings.smtp_password)

        with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, password)
            server.send_message(msg)

        logger.info(f"Email sent to {recipients}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def generate_ai_suggestions(
    name: str, age: int = None, note: str = None, api_key: str = ""
):
    """Generate gift suggestions and a congratulations message using OpenAI."""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        # Build context for the AI
        context_parts = [f"Person's name: {name}"]
        if age:
            context_parts.append(f"Turning {age} years old")
        if note:
            context_parts.append(f"Additional info: {note}")

        context = ". ".join(context_parts)

        prompt = f"""Given the following information about someone celebrating a birthday:
{context}

Please provide:
1. A warm, personalized birthday congratulations message (1 paragraph, 2-3 sentences)
2. 5 thoughtful gift suggestions appropriate for their age and context

Format your response exactly as:
MESSAGE: [your congratulations message here]

GIFTS:
1. [Gift idea 1]
2. [Gift idea 2]
3. [Gift idea 3]
4. [Gift idea 4]
5. [Gift idea 5]

Keep the tone warm and friendly. Consider cultural appropriateness and age-appropriateness."""

        response = client.chat.completions.create(
            model="gpt-4o",  # Full flagship model for best quality
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that creates personalized birthday messages and gift suggestions.",
                },
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=500,  # gpt-4o uses max_completion_tokens instead of max_tokens
            temperature=0.7,
        )

        result = response.choices[0].message.content

        # Parse the response
        message_match = re.search(r"MESSAGE:\s*(.+?)(?=GIFTS:)", result, re.DOTALL)
        gifts_match = re.search(r"GIFTS:\s*(.+)", result, re.DOTALL)

        message = message_match.group(1).strip() if message_match else ""
        gifts_text = gifts_match.group(1).strip() if gifts_match else ""

        # Parse gift list
        gifts = []
        for line in gifts_text.split("\n"):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                # Remove numbering
                gift = re.sub(r"^\d+\.\s*|\-\s*", "", line)
                gifts.append(gift)

        return {
            "message": message,
            "gifts": gifts[:5],  # Ensure max 5 gifts
        }

    except Exception as e:
        logger.error(f"Failed to generate AI suggestions: {e}")
        return None


def check_and_send_reminders():
    """Check for upcoming birthdays and send reminders."""
    try:
        settings = settings_storage.get_email_settings()

        if not settings.enabled:
            logger.debug("Email notifications disabled")
            return

        if not settings.recipients:
            logger.warning("No email recipients configured")
            return

        # Get tomorrow's date
        tomorrow = datetime.now() + timedelta(days=1)
        tomorrow_month = tomorrow.month
        tomorrow_day = tomorrow.day
        current_year = tomorrow.year

        # Find birthdays tomorrow (skip entries with null day)
        all_birthdays = birthday_storage.get_all()
        upcoming_birthdays = [
            b
            for b in all_birthdays
            if b.day is not None and b.month == tomorrow_month and b.day == tomorrow_day
        ]

        if not upcoming_birthdays:
            logger.debug(f"No birthdays tomorrow ({tomorrow_month}/{tomorrow_day})")
            return

        # Build email content
        subject = f"Birthday Reminder - {len(upcoming_birthdays)} birthday(s) tomorrow"

        body_lines = [
            "<html><body>",
            f"<h2>🎂 Birthday Reminder for {tomorrow.strftime('%B %d, %Y')}</h2>",
            "<p>The following people have birthdays tomorrow:</p>",
            "<ul>",
        ]

        for birthday in upcoming_birthdays:
            age_info = ""
            age_value = None
            if birthday.birth_year:
                age_value = calculate_age(birthday.birth_year, current_year)
                age_info = f" (turning {age_value})"

            note_info = ""
            if birthday.note:
                note_info = f" - <i>{birthday.note}</i>"

            body_lines.append(
                f"<li><strong>{birthday.name}</strong>{age_info}{note_info}"
            )

            # Add AI-generated suggestions if enabled
            if settings.ai_enabled and settings.openai_api_key:
                ai_suggestions = generate_ai_suggestions(
                    birthday.name, age_value, birthday.note, settings.openai_api_key
                )

                if ai_suggestions:
                    # Add personalized message
                    if ai_suggestions.get("message"):
                        body_lines.append(
                            f"<br><br><em>💭 {ai_suggestions['message']}</em>"
                        )

                    # Add gift suggestions
                    if ai_suggestions.get("gifts"):
                        body_lines.append(
                            "<br><br><strong>🎁 Gift Ideas:</strong><ul style='margin-top: 5px;'>"
                        )
                        for gift in ai_suggestions["gifts"]:
                            body_lines.append(f"<li>{gift}</li>")
                        body_lines.append("</ul>")

            body_lines.append("</li>")

        body_lines.extend(
            [
                "</ul>",
                "<p><small>This is an automated reminder from your Birthday Tracker.</small></p>",
                "</body></html>",
            ]
        )

        body = "\n".join(body_lines)

        # Send email
        recipients = settings.recipients
        if settings.test_mode:
            logger.info(
                "Test mode enabled - email would be sent to: " + str(recipients)
            )
            logger.info(f"Subject: {subject}")
            logger.info(f"Body: {body}")
        else:
            send_email(subject, body, recipients, settings)

        logger.info(f"Processed {len(upcoming_birthdays)} birthday reminders")

    except Exception as e:
        logger.error(f"Error in check_and_send_reminders: {e}")


def start_scheduler():
    """Start the birthday reminder scheduler."""
    global scheduler

    if scheduler is not None:
        logger.warning("Scheduler already running")
        return

    scheduler = BackgroundScheduler()

    # Get the configured reminder time
    settings = settings_storage.get_email_settings()
    reminder_time = settings.reminder_time or "09:00"

    try:
        hour, minute = map(int, reminder_time.split(":"))
    except (ValueError, AttributeError):
        hour, minute = 9, 0  # Default to 9 AM
        logger.warning(f"Invalid reminder_time format '{reminder_time}', using 09:00")

    # Schedule the job to run daily at the configured time
    trigger = CronTrigger(hour=hour, minute=minute)
    scheduler.add_job(
        check_and_send_reminders,
        trigger=trigger,
        id="birthday_reminder",
        name="Birthday Reminder Check",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        f"Birthday reminder scheduler started (checks daily at {hour:02d}:{minute:02d})"
    )


def stop_scheduler():
    """Stop the scheduler."""
    global scheduler
    if scheduler is not None:
        scheduler.shutdown()
        scheduler = None
        logger.info("Scheduler stopped")


def reschedule_reminders():
    """Reschedule reminders (called when settings change)."""
    if scheduler is not None:
        stop_scheduler()
    start_scheduler()
