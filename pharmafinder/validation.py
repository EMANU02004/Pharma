"""Small input-validation helpers. All validation runs on the server."""
import re
from datetime import date, datetime

from flask import request

from .errors import ApiError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?\d{9,15}$")


def json_body():
    if not request.is_json:
        raise ApiError("Request body must be JSON (Content-Type: application/json)", 415)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object")
    return data


def require_fields(data, *names):
    missing = {n: "This field is required" for n in names
               if data.get(n) is None or (isinstance(data.get(n), str) and not data[n].strip())}
    if missing:
        raise ApiError("Missing required fields", 422, missing)


def clean_str(value, name, max_len, required=True):
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ApiError(f"{name} is required", 422, {name: "required"})
        return None
    if not isinstance(value, str):
        raise ApiError(f"{name} must be text", 422, {name: "must be text"})
    value = value.strip()
    if len(value) > max_len:
        raise ApiError(f"{name} is too long (max {max_len})", 422, {name: "too long"})
    return value


def as_int(value, name, minimum=None, maximum=None):
    if isinstance(value, bool):
        raise ApiError(f"{name} must be a whole number", 422, {name: "must be a whole number"})
    try:
        number = int(value)
        if isinstance(value, float) and not value.is_integer():
            raise ValueError
        if isinstance(value, str) and not value.strip().lstrip("-").isdigit():
            raise ValueError
    except (TypeError, ValueError):
        raise ApiError(f"{name} must be a whole number", 422, {name: "must be a whole number"})
    if minimum is not None and number < minimum:
        raise ApiError(f"{name} must be at least {minimum}", 422, {name: f"min {minimum}"})
    if maximum is not None and number > maximum:
        raise ApiError(f"{name} must be at most {maximum}", 422, {name: f"max {maximum}"})
    return number


def as_price(value, name="price_kes"):
    try:
        price = round(float(value), 2)
    except (TypeError, ValueError):
        raise ApiError(f"{name} must be a number", 422, {name: "must be a number"})
    if isinstance(value, bool) or price <= 0 or price > 1_000_000:
        raise ApiError(f"{name} must be greater than 0", 422, {name: "must be > 0"})
    return price


def as_float(value, name, minimum, maximum):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ApiError(f"{name} must be a number", 422, {name: "must be a number"})
    if not (minimum <= number <= maximum):
        raise ApiError(f"{name} is out of range", 422, {name: "out of range"})
    return number


def as_date(value, name):
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ApiError(f"{name} must be a date (YYYY-MM-DD)", 422, {name: "invalid date"})


def as_email(value):
    email = clean_str(value, "email", 160).lower()
    if not EMAIL_RE.match(email):
        raise ApiError("Enter a valid email address", 422, {"email": "invalid"})
    return email


def as_password(value):
    if not isinstance(value, str) or len(value) < 8:
        raise ApiError("Password must be at least 8 characters", 422, {"password": "min 8 chars"})
    if len(value) > 128:
        raise ApiError("Password is too long", 422, {"password": "too long"})
    if not (re.search(r"[A-Za-z]", value) and re.search(r"\d", value)):
        raise ApiError("Password must contain letters and numbers", 422,
                       {"password": "letters and numbers"})
    return value


def as_phone(value):
    if value in (None, ""):
        return None
    phone = str(value).replace(" ", "")
    if not PHONE_RE.match(phone):
        raise ApiError("Enter a valid phone number", 422, {"phone": "invalid"})
    return phone
