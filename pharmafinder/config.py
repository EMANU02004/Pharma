"""Configuration read from environment variables (see .env.example)."""
import os


def _bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

    DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.environ.get("DB_PORT", "3306"))
    DB_USER = os.environ.get("DB_USER", "pharma")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "pharma_dev")
    DB_NAME = os.environ.get("DB_NAME", "pharmafinder")
    # Path to a CA certificate when the host requires TLS (e.g. Aiven).
    DB_SSL_CA = os.environ.get("DB_SSL_CA") or None

    # Session cookie hardening
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8  # 8 hours

    # Optional email delivery for notifications. Without SMTP_HOST,
    # notifications are stored in-app and marked "simulated".
    SMTP_HOST = os.environ.get("SMTP_HOST") or None
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER") or None
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD") or None
    SMTP_FROM = os.environ.get("SMTP_FROM", "PharmaFinder <no-reply@pharmafinder.local>")

    # Business rules
    PRESCRIPTION_DEFAULT_VALID_DAYS = 30
    PRESCRIPTION_MAX_VALID_DAYS = 90
    GRANT_DEFAULT_HOURS = 24
    GRANT_MAX_HOURS = 72
    LOW_STOCK_THRESHOLD = 10
    # Brute-force limits (counted from the audit log, so they work on serverless hosts)
    MAX_FAILED_LOGINS = 5
    MAX_FAILED_CODE_CHECKS = 10
    FAILED_ATTEMPT_WINDOW_MINUTES = 15
    TIMEZONE = "Africa/Nairobi"

    TESTING = False
