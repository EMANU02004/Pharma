"""Notifications.

Every notification is stored in the `notifications` table and shown in the
user's dashboard. If SMTP settings are configured, an email copy is also sent and
the row is marked 'delivered' (or 'failed'). Without SMTP settings the email is
NOT sent and the row is marked 'simulated' - the UI labels it that way.
"""
import smtplib
from email.message import EmailMessage

from flask import current_app

from .db import execute


def _send_email(to_addr, subject, body):
    cfg = current_app.config
    msg = EmailMessage()
    msg["From"] = cfg["SMTP_FROM"]
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=10) as smtp:
        smtp.starttls()
        if cfg["SMTP_USER"]:
            smtp.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
        smtp.send_message(msg)


def notify(user_id, email, subject, body):
    """Store an in-app notification and, when configured, send an email copy."""
    if current_app.config.get("SMTP_HOST") and email:
        try:
            _send_email(email, subject, body)
            status = "delivered"
        except Exception:  # never let email failure break the main action
            current_app.logger.exception("Email delivery failed")
            status = "failed"
        channel = "email"
    else:
        status = "simulated"
        channel = "in_app"
    execute(
        "INSERT INTO notifications (user_id, channel, subject, body, delivery_status) "
        "VALUES (%s, %s, %s, %s, %s)",
        (user_id, channel, subject[:160], body[:1000], status),
    )
    return status
