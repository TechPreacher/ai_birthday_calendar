"""Settings routes."""

from fastapi import APIRouter, Depends, HTTPException

from ..models import (
    SECRET_PLACEHOLDER,
    SECRET_SETTING_FIELDS,
    EmailSettings,
    User,
)
from ..auth import get_current_active_user
from ..storage import settings_storage
from ..scheduler import reschedule_reminders

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _without_secrets(settings: EmailSettings) -> EmailSettings:
    """Replace stored secrets with a placeholder for sending to a client.

    A secret that is not set stays empty, so the settings screen can still
    show at a glance whether one is configured.
    """
    data = settings.model_dump()
    for field in SECRET_SETTING_FIELDS:
        if data.get(field):
            data[field] = SECRET_PLACEHOLDER
    return EmailSettings(**data)


def _restore_unchanged_secrets(
    incoming: EmailSettings, stored: EmailSettings
) -> EmailSettings:
    """Put back any secret the client echoed unchanged.

    The client is sent a placeholder rather than the real value, so saving the
    form untouched would otherwise overwrite the SMTP password and the OpenAI
    key with that placeholder. Any other value is taken at face value, so an
    empty string still clears a secret deliberately.
    """
    data = incoming.model_dump()
    for field in SECRET_SETTING_FIELDS:
        if data.get(field) == SECRET_PLACEHOLDER:
            data[field] = getattr(stored, field)
    return EmailSettings(**data)


@router.get("/email", response_model=EmailSettings)
async def get_email_settings(current_user: User = Depends(get_current_active_user)):
    """Get email notification settings.

    Secrets are masked. They were previously returned in the clear, which put
    the SMTP password and the OpenAI API key into the browser of every admin
    who opened the settings screen -- and into anything that could read from
    there.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return _without_secrets(settings_storage.get_email_settings())


@router.put("/email", response_model=EmailSettings)
async def update_email_settings(
    settings: EmailSettings, current_user: User = Depends(get_current_active_user)
):
    """Update email notification settings."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    stored = settings_storage.get_email_settings()
    to_save = _restore_unchanged_secrets(settings, stored)
    settings_storage.save_email_settings(to_save)

    # Reschedule reminders with new time
    reschedule_reminders()

    # Masked on the way out too, so the response cannot leak what the request
    # deliberately withheld.
    return _without_secrets(to_save)


@router.post("/email/test")
async def test_email(current_user: User = Depends(get_current_active_user)):
    """Send a test email immediately."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    # Import send_email function
    from ..scheduler import send_email

    # Get settings
    settings = settings_storage.get_email_settings()

    if not settings.enabled:
        raise HTTPException(status_code=400, detail="Email notifications are disabled")

    if not settings.recipients:
        raise HTTPException(status_code=400, detail="No recipients configured")

    # Send a real test email
    subject = "🎂 Birthday Tracker - Test Email"
    body = """
    <html>
    <body>
        <h2>🎂 Birthday Tracker - Test Email</h2>
        <p>This is a test email from your Birthday Tracker application.</p>
        <p><strong>If you received this, your email configuration is working correctly!</strong></p>
        <hr>
        <p><small>Sent from Birthday Tracker</small></p>
    </body>
    </html>
    """

    success = send_email(subject, body, settings.recipients, settings)

    if success:
        return {
            "message": f"Test email sent to {len(settings.recipients)} recipient(s)"
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to send test email. Check server logs for details.",
        )


@router.post("/email/test-ai")
async def test_email_with_ai(current_user: User = Depends(get_current_active_user)):
    """Send a test email with AI-generated content using the next upcoming birthday."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    from ..scheduler import send_email, generate_ai_suggestions, calculate_age, esc
    from ..storage import birthday_storage
    from datetime import datetime

    from ..dates import next_occurrence

    # Get settings
    settings = settings_storage.get_email_settings()

    if not settings.enabled:
        raise HTTPException(status_code=400, detail="Email notifications are disabled")

    if not settings.recipients:
        raise HTTPException(status_code=400, detail="No recipients configured")

    if not settings.ai_enabled:
        raise HTTPException(status_code=400, detail="AI features are not enabled")

    if not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key is not configured")

    # Find the next upcoming birthday
    today = datetime.now()
    all_birthdays = birthday_storage.get_all()

    # Filter birthdays with valid days and sort by days until birthday
    valid_birthdays = [b for b in all_birthdays if b.day is not None]

    if not valid_birthdays:
        raise HTTPException(status_code=400, detail="No birthdays found in the system")

    # Find next birthday
    next_birthday = None
    next_birthday_date = None
    min_days = float("inf")

    for birthday in valid_birthdays:
        # next_occurrence handles February 29, which has no date at all in a
        # non-leap year -- datetime(2026, 2, 29) raises, which surfaced here as
        # a 500 from this endpoint.
        occurrence = next_occurrence(birthday.month, birthday.day, today.date())
        days_until = (occurrence - today.date()).days

        if days_until < min_days:
            min_days = days_until
            next_birthday = birthday
            next_birthday_date = occurrence

    if not next_birthday:
        raise HTTPException(
            status_code=400, detail="Could not find an upcoming birthday"
        )

    # Calculate age
    age_info = ""
    age_value = None
    if next_birthday.birth_year:
        # The year the birthday will occur, taken from the occurrence already
        # computed above rather than rebuilt from a possibly impossible date.
        age_value = calculate_age(next_birthday.birth_year, next_birthday_date.year)
        age_info = f" (turning {age_value})"

    # Generate AI suggestions
    try:
        ai_suggestions = generate_ai_suggestions(
            next_birthday.name, age_value, next_birthday.note, settings.openai_api_key
        )
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
            raise HTTPException(
                status_code=402,
                detail="OpenAI API quota exceeded. Please add billing or increase your spending limit at https://platform.openai.com/settings/organization/billing",
            )
        elif "401" in error_msg or "invalid" in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail="Invalid OpenAI API key. Please check your key at https://platform.openai.com/api-keys",
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate AI suggestions: {error_msg}",
            )

    if not ai_suggestions:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate AI suggestions. The AI returned no content. Check your API key and server logs.",
        )

    # Build test email
    birthday_date = next_birthday_date

    subject = "🎂 Birthday Tracker - AI Test (Next Upcoming Birthday)"

    body_lines = [
        "<html><body>",
        "<h2>🎂 AI Feature Test - Next Upcoming Birthday</h2>",
        "<p><em>This is a test email showing how AI will enhance your birthday reminders.</em></p>",
        f"<p><strong>Next birthday: {birthday_date.strftime('%B %d, %Y')} ({min_days} days away)</strong></p>",
        "<hr>",
        "<ul>",
        f"<li><strong>{esc(next_birthday.name)}</strong>{age_info}",
    ]

    if next_birthday.note:
        body_lines.append(f" - <i>{esc(next_birthday.note)}</i>")

    # Add AI-generated content
    if ai_suggestions.get("message"):
        body_lines.append(f"<br><br><em>💭 {esc(ai_suggestions['message'])}</em>")

    if ai_suggestions.get("gifts"):
        body_lines.append(
            "<br><br><strong>🎁 Gift Ideas:</strong><ul style='margin-top: 5px;'>"
        )
        for gift in ai_suggestions["gifts"]:
            body_lines.append(f"<li>{esc(gift)}</li>")
        body_lines.append("</ul>")

    body_lines.extend(
        [
            "</li>",
            "</ul>",
            "<hr>",
            "<p><small>This is a test email from your Birthday Tracker showing AI-enhanced content.</small></p>",
            "</body></html>",
        ]
    )

    body = "\n".join(body_lines)

    # Send the email
    success = send_email(subject, body, settings.recipients, settings)

    if success:
        return {
            "message": f"AI test email sent to {len(settings.recipients)} recipient(s)",
            "birthday_tested": next_birthday.name,
            "days_until": min_days,
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to send test email. Check server logs for details.",
        )
