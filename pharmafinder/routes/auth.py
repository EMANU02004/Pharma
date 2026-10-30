"""Registration (patients only), login, logout and current-user endpoints."""
from flask import Blueprint, current_app, jsonify, session

from ..audit import log_action
from ..db import commit, execute, query_one, transaction
from ..errors import ApiError
from ..security import current_user, hash_password, login_required, recent_failures, verify_password
from ..validation import as_date, as_email, as_password, as_phone, clean_str, json_body

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/register")
def register():
    """Self-registration always creates a PATIENT account.

    Doctors and pharmacists are pre-registered by an administrator, so any
    'role' in the request body is ignored.
    """
    data = json_body()
    full_name = clean_str(data.get("full_name"), "full_name", 120)
    email = as_email(data.get("email"))
    password = as_password(data.get("password"))
    phone = as_phone(data.get("phone"))
    dob = as_date(data["date_of_birth"], "date_of_birth") if data.get("date_of_birth") else None
    sub_county = clean_str(data.get("sub_county"), "sub_county", 80, required=False)

    if query_one("SELECT 1 FROM users WHERE email=%s", (email,)):
        raise ApiError("An account with this email already exists", 409, {"email": "taken"})

    with transaction():
        user_id = execute(
            "INSERT INTO users (full_name, email, phone, password_hash, role) "
            "VALUES (%s, %s, %s, %s, 'patient')",
            (full_name, email, phone, hash_password(password)),
        )
        patient_id = execute(
            "INSERT INTO patients (user_id, date_of_birth, sub_county) VALUES (%s, %s, %s)",
            (user_id, dob, sub_county),
        )
        log_action(user_id, "REGISTER", "patient", patient_id,
                   "role request ignored" if data.get("role") not in (None, "patient") else None)

    session.clear()
    session["user_id"] = user_id
    session.permanent = True
    return jsonify({"user_id": user_id, "role": "patient", "full_name": full_name}), 201


@bp.post("/login")
def login():
    data = json_body()
    email = str(data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        raise ApiError("Email and password are required", 422)

    if recent_failures("LOGIN_FAILED", details=email) >= current_app.config["MAX_FAILED_LOGINS"]:
        raise ApiError("Too many failed attempts. Try again in 15 minutes.", 429)

    user = query_one(
        "SELECT user_id, full_name, role, password_hash, is_active FROM users WHERE email=%s",
        (email,),
    )
    if not user or not verify_password(user["password_hash"], password):
        log_action(user["user_id"] if user else None, "LOGIN_FAILED", "user", None, email)
        commit()
        raise ApiError("Incorrect email or password", 401)
    if not user["is_active"]:
        raise ApiError("This account has been deactivated", 403)

    log_action(user["user_id"], "LOGIN", "user", user["user_id"])
    commit()
    session.clear()
    session["user_id"] = user["user_id"]
    session.permanent = True
    return jsonify({"user_id": user["user_id"], "role": user["role"], "full_name": user["full_name"]})


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@bp.get("/me")
@login_required
def me():
    user = dict(current_user())
    if user["role"] == "pharmacist" and user.get("pharmacy_id"):
        pharmacy = query_one("SELECT name FROM pharmacies WHERE pharmacy_id=%s", (user["pharmacy_id"],))
        user["pharmacy_name"] = pharmacy["name"] if pharmacy else None
    if user["role"] == "patient":
        p = query_one("SELECT date_of_birth, sub_county FROM patients WHERE patient_id=%s",
                      (user["patient_id"],))
        user.update(p or {})
    return jsonify(user)
