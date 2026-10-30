"""Authentication and role-based access control, enforced on the server."""
from functools import wraps

from flask import current_app, g, session
from werkzeug.security import check_password_hash, generate_password_hash

from .db import query_one
from .errors import ApiError

ROLES = ("patient", "doctor", "pharmacist", "admin")


def hash_password(password):
    return generate_password_hash(password)  # scrypt with a random salt


def verify_password(password_hash, password):
    return check_password_hash(password_hash, password)


def load_current_user():
    """Look the user up on every request so deactivation takes effect immediately."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = query_one(
        "SELECT user_id, full_name, email, phone, role, is_active FROM users WHERE user_id = %s",
        (user_id,),
    )
    if not user or not user["is_active"]:
        session.clear()
        return None
    # Attach the role-specific id (patient_id, doctor_id, pharmacist_id + pharmacy_id)
    if user["role"] == "patient":
        row = query_one("SELECT patient_id FROM patients WHERE user_id=%s", (user_id,))
        user["patient_id"] = row["patient_id"] if row else None
    elif user["role"] == "doctor":
        row = query_one("SELECT doctor_id FROM doctors WHERE user_id=%s", (user_id,))
        user["doctor_id"] = row["doctor_id"] if row else None
    elif user["role"] == "pharmacist":
        row = query_one(
            "SELECT pharmacist_id, pharmacy_id FROM pharmacists WHERE user_id=%s", (user_id,)
        )
        user["pharmacist_id"] = row["pharmacist_id"] if row else None
        user["pharmacy_id"] = row["pharmacy_id"] if row else None
    return user


def current_user():
    if "user" not in g:
        g.user = load_current_user()
    return g.user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            raise ApiError("Login required", 401)
        return view(*args, **kwargs)
    return wrapper


def roles_required(*roles):
    """Reject the request with 403 unless the logged-in user has one of `roles`."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                raise ApiError("Login required", 401)
            if user["role"] not in roles:
                raise ApiError("You do not have permission to do this", 403)
            return view(*args, **kwargs)
        return wrapper
    return decorator


def recent_failures(action, user_id=None, details=None):
    """Count recent failed attempts recorded in the audit log."""
    window = current_app.config["FAILED_ATTEMPT_WINDOW_MINUTES"]
    if user_id is not None:
        row = query_one(
            "SELECT COUNT(*) AS n FROM audit_log WHERE action=%s AND user_id=%s "
            "AND created_at > NOW() - INTERVAL %s MINUTE",
            (action, user_id, window),
        )
    else:
        row = query_one(
            "SELECT COUNT(*) AS n FROM audit_log WHERE action=%s AND details=%s "
            "AND created_at > NOW() - INTERVAL %s MINUTE",
            (action, details, window),
        )
    return row["n"]
