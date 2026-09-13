"""HTML and plaintext bodies for outbound photographer emails."""

from __future__ import annotations

from html import escape


def otp_email_content(
    *,
    app_name: str,
    otp: str,
    purpose_label: str,
    expiry_minutes: int,
) -> tuple[str, str, str]:
    """Return subject, plaintext, and HTML for an OTP email.

    Args:
        app_name: Product name shown in the message.
        otp: Six-digit one-time code.
        purpose_label: Human-readable purpose (login, registration, reset).
        expiry_minutes: How long the code remains valid.

    Returns:
        Tuple of subject, plaintext body, and HTML body.
    """
    safe_app = escape(app_name)
    safe_otp = escape(otp)
    safe_purpose = escape(purpose_label)
    subject = f"Your {app_name} {purpose_label} code"
    text = (
        f"Your {app_name} {purpose_label} code is {otp}.\n\n"
        f"This code expires in {expiry_minutes} minutes. "
        "If you did not request it, you can ignore this email.\n"
    )
    html = f"""<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; color: #111; line-height: 1.5;">
  <p>Your <strong>{safe_app}</strong> {safe_purpose} code is:</p>
  <p style="font-size: 28px; letter-spacing: 0.3em; font-weight: bold;">{safe_otp}</p>
  <p>This code expires in {expiry_minutes} minutes.</p>
  <p style="color: #666; font-size: 13px;">If you did not request this, you can ignore this email.</p>
</body>
</html>
"""
    return subject, text, html


def processing_complete_email_content(
    *,
    studio_name: str,
    event_name: str,
    photo_count: int,
    event_url: str,
    app_name: str,
) -> tuple[str, str, str]:
    """Return subject, plaintext, and HTML for the processing-complete email.

    Args:
        studio_name: Photographer studio display name.
        event_name: Event title.
        photo_count: Total photos on the event.
        event_url: Dashboard URL for the event.
        app_name: Product name shown in the footer.

    Returns:
        Tuple of subject, plaintext body, and HTML body.
    """
    safe_studio = escape(studio_name)
    safe_event = escape(event_name)
    safe_url = escape(event_url, quote=True)
    safe_app = escape(app_name)
    subject = f"Event Processing Complete: {event_name}"
    text = (
        f"Hello {studio_name},\n\n"
        f"Great news! Your event '{event_name}' has finished processing.\n"
        f"All {photo_count} photos have been processed and facial recognition is complete.\n\n"
        f"Review and share the gallery:\n{event_url}\n"
    )
    html = f"""<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; color: #111; line-height: 1.5;">
  <p>Hello {safe_studio},</p>
  <p>Great news! Your event <strong>{safe_event}</strong> has finished processing.</p>
  <p>All {photo_count} photos have been processed and facial recognition is complete.</p>
  <p><a href="{safe_url}" style="display: inline-block; background: #111; color: #fff;
     padding: 10px 16px; text-decoration: none; border-radius: 6px;">Open event dashboard</a></p>
  <p style="color: #666; font-size: 13px;">{safe_url}</p>
  <p style="color: #666; font-size: 13px;">— {safe_app}</p>
</body>
</html>
"""
    return subject, text, html
