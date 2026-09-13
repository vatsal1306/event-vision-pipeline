"""Send one test message through the configured SMTP adapter.

On the CPU host (repo root):

    docker compose -f docker-compose.prod.yml exec backend \\
      python -m app.cli.smtp_check --to you@example.com

If ``--to`` is omitted, the message is sent to ``EMAIL_FROM`` (self-test).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.config import get_settings
from app.services.email_service import EmailService


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(
        prog="python -m app.cli.smtp_check",
        description="Send a one-shot SMTP test email using server env vars.",
    )
    parser.add_argument(
        "--to",
        default="",
        help="Recipient. Defaults to EMAIL_FROM so you can inbox-check the mailbox itself.",
    )
    return parser


async def _send_test(to: str) -> int:
    """Send the probe email and print a pass/fail summary.

    Args:
        to: Recipient address.

    Returns:
        Process exit code (0 success, 1 failure).
    """
    settings = get_settings()
    password_len = len(settings.smtp_password.replace(" ", ""))
    print("SMTP probe")
    print(f"  EMAIL_PROVIDER={settings.email_provider}")
    print(f"  SMTP_HOST={settings.smtp_host}:{settings.smtp_port}")
    print(f"  SMTP_USER={settings.smtp_user or '(empty)'}")
    print(f"  EMAIL_FROM={settings.email_from}")
    print(f"  SMTP_PASSWORD_LENGTH={password_len} (spaces stripped; value not printed)")
    print(f"  TO={to}")

    service = EmailService(settings)
    body = (
        "SpotMe SMTP probe. If you received this, registration email OTPs can send.\n"
    )
    html = "<p>SpotMe SMTP probe. If you received this, registration email OTPs can send.</p>"
    ok = await service.send(
        to=to,
        subject="SpotMe SMTP probe",
        body=body,
        html_body=html,
    )
    if ok:
        print("RESULT=ok  Check the inbox (and spam) for subject: SpotMe SMTP probe")
        return 0

    hint = service.last_user_message or "SMTP send returned false. See backend logs for smtp_message."
    print(f"RESULT=fail  {hint}")
    return 1


def main() -> None:
    """Parse args and run the probe."""
    args = build_parser().parse_args()
    settings = get_settings()
    to = args.to.strip() or settings.email_from
    if not to:
        print("Pass --to someone@example.com or set EMAIL_FROM.", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(_send_test(to)))


if __name__ == "__main__":
    main()
