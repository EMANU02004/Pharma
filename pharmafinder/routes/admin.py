"""Administrator endpoints: create staff accounts and pharmacies, manage users, audit log."""
import re
from flask import Blueprint, jsonify, request

from ..audit import log_action
from ..db import execute, query, query_one, transaction
from ..errors import ApiError
from ..security import ROLES, current_user, hash_password, roles_required
from ..validation import as_email, as_float, as_int, as_password, as_phone, clean_str, json_body

bp = Blueprint("admin", __name__, url_prefix="/api/admin")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


@bp.get("/stats")
@roles_required("admin")
def stats():
    counts = {r["role"]: r["n"] for r in query("SELECT role, COUNT(*) n FROM users GROUP BY role")}
    rx = {r["status"]: r["n"] for r in query("SELECT status, COUNT(*) n FROM prescriptions GROUP BY status")}
    return jsonify({
        "users": counts,
        "prescriptions": rx,
        "pharmacies": query_one("SELECT COUNT(*) n FROM pharmacies WHERE is_active=TRUE")["n"],
        "medicines": query_one("SELECT COUNT(*) n FROM medicines")["n"],
        "audit_events_24h": query_one(
            "SELECT COUNT(*) n FROM audit_log WHERE created_at > NOW() - INTERVAL 1 DAY")["n"],
    })


@bp.get("/users")
@roles_required("admin")
def users():
    role = request.args.get("role")
    q = f"%{(request.args.get('q') or '').strip()}%"
    params = [q, q]
    sql = """SELECT u.user_id, u.full_name, u.email, u.phone, u.role, u.is_active, u.created_at,
                    d.license_number AS doctor_license, d.facility,
                    ph.name AS pharmacy_name
             FROM users u
             LEFT JOIN doctors d ON d.user_id = u.user_id
             LEFT JOIN pharmacists pc ON pc.user_id = u.user_id
             LEFT JOIN pharmacies ph ON ph.pharmacy_id = pc.pharmacy_id
             WHERE (u.full_name LIKE %s OR u.email LIKE %s)"""
    if role:
        if role not in ROLES:
            raise ApiError("Unknown role", 422)
        sql += " AND u.role = %s"
        params.append(role)
    sql += " ORDER BY u.role, u.full_name LIMIT 200"
    return jsonify(query(sql, tuple(params)))


def _new_user(data, role):
    full_name = clean_str(data.get("full_name"), "full_name", 120)
    email = as_email(data.get("email"))
    password = as_password(data.get("password"))
    phone = as_phone(data.get("phone"))
    if query_one("SELECT 1 FROM users WHERE email=%s", (email,)):
        raise ApiError("An account with this email already exists", 409, {"email": "taken"})
    return execute(
        "INSERT INTO users (full_name, email, phone, password_hash, role) VALUES (%s,%s,%s,%s,%s)",
        (full_name, email, phone, hash_password(password), role),
    )


@bp.post("/doctors")
@roles_required("admin")
def create_doctor():
    data = json_body()
    license_number = clean_str(data.get("license_number"), "license_number", 40)
    speciality = clean_str(data.get("speciality"), "speciality", 80, required=False)
    facility = clean_str(data.get("facility"), "facility", 120, required=False)
    if query_one("SELECT 1 FROM doctors WHERE license_number=%s", (license_number,)):
        raise ApiError("A doctor with this license number already exists", 409)
    with transaction():
        user_id = _new_user(data, "doctor")
        doctor_id = execute(
            "INSERT INTO doctors (user_id, license_number, speciality, facility) VALUES (%s,%s,%s,%s)",
            (user_id, license_number, speciality, facility))
        log_action(current_user()["user_id"], "CREATE_DOCTOR", "user", user_id, license_number)
    return jsonify({"user_id": user_id, "doctor_id": doctor_id}), 201


@bp.post("/pharmacies")
@roles_required("admin")
def create_pharmacy():
    data = json_body()
    name = clean_str(data.get("name"), "name", 120)
    license_number = clean_str(data.get("license_number"), "license_number", 40)
    address = clean_str(data.get("address"), "address", 200)
    lat = as_float(data.get("latitude"), "latitude", -90, 90)
    lng = as_float(data.get("longitude"), "longitude", -180, 180)
    open_days = clean_str(data.get("open_days") or "Mon-Sat", "open_days", 40)
    opens_at = clean_str(data.get("opens_at") or "08:00", "opens_at", 5)
    closes_at = clean_str(data.get("closes_at") or "20:00", "closes_at", 5)
    for field, value in (("opens_at", opens_at), ("closes_at", closes_at)):
        if not TIME_RE.match(value):
            raise ApiError(f"{field} must be HH:MM", 422, {field: "HH:MM"})
    if query_one("SELECT 1 FROM pharmacies WHERE license_number=%s", (license_number,)):
        raise ApiError("A pharmacy with this license number already exists", 409)
    with transaction():
        pid = execute(
            """INSERT INTO pharmacies (name, license_number, address, latitude, longitude,
                                       open_days, opens_at, closes_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (name, license_number, address, lat, lng, open_days, opens_at, closes_at))
        log_action(current_user()["user_id"], "CREATE_PHARMACY", "pharmacy", pid, name)
    return jsonify({"pharmacy_id": pid}), 201


@bp.get("/pharmacies")
@roles_required("admin")
def list_pharmacies():
    rows = query("""SELECT ph.*, (SELECT COUNT(*) FROM pharmacists p WHERE p.pharmacy_id=ph.pharmacy_id) AS staff,
                           (SELECT COUNT(*) FROM item_stock s WHERE s.pharmacy_id=ph.pharmacy_id) AS stock_lines
                    FROM pharmacies ph ORDER BY ph.name""")
    for r in rows:
        r["latitude"], r["longitude"] = float(r["latitude"]), float(r["longitude"])
    return jsonify(rows)


@bp.post("/pharmacists")
@roles_required("admin")
def create_pharmacist():
    data = json_body()
    pharmacy_id = as_int(data.get("pharmacy_id"), "pharmacy_id", 1)
    license_number = clean_str(data.get("license_number"), "license_number", 40)
    if not query_one("SELECT 1 FROM pharmacies WHERE pharmacy_id=%s", (pharmacy_id,)):
        raise ApiError("Pharmacy not found", 404)
    if query_one("SELECT 1 FROM pharmacists WHERE license_number=%s", (license_number,)):
        raise ApiError("A pharmacist with this license number already exists", 409)
    with transaction():
        user_id = _new_user(data, "pharmacist")
        pharmacist_id = execute(
            "INSERT INTO pharmacists (user_id, pharmacy_id, license_number) VALUES (%s,%s,%s)",
            (user_id, pharmacy_id, license_number))
        log_action(current_user()["user_id"], "CREATE_PHARMACIST", "user", user_id,
                   f"pharmacy_id={pharmacy_id}")
    return jsonify({"user_id": user_id, "pharmacist_id": pharmacist_id}), 201


@bp.post("/users/<int:user_id>/status")
@roles_required("admin")
def set_status(user_id):
    admin = current_user()
    data = json_body()
    if "is_active" not in data or not isinstance(data["is_active"], bool):
        raise ApiError("is_active must be true or false", 422)
    if user_id == admin["user_id"]:
        raise ApiError("You cannot deactivate your own account", 409)
    with transaction():
        if not query_one("SELECT 1 FROM users WHERE user_id=%s", (user_id,)):
            raise ApiError("User not found", 404)
        execute("UPDATE users SET is_active=%s WHERE user_id=%s", (data["is_active"], user_id))
        log_action(admin["user_id"], "ACTIVATE_USER" if data["is_active"] else "DEACTIVATE_USER",
                   "user", user_id)
    return jsonify({"user_id": user_id, "is_active": data["is_active"]})


@bp.get("/audit")
@roles_required("admin")
def audit_log():
    action = request.args.get("action")
    limit = as_int(request.args.get("limit", 100), "limit", 1, 500)
    sql = """SELECT a.log_id, a.created_at, a.user_id, u.full_name, u.role, a.action,
                    a.target_type, a.target_id, a.details
             FROM audit_log a LEFT JOIN users u ON u.user_id = a.user_id"""
    params = []
    if action:
        sql += " WHERE a.action = %s"
        params.append(action)
    sql += " ORDER BY a.log_id DESC LIMIT %s"
    params.append(limit)
    rows = query(sql, tuple(params))
    actions = [r["action"] for r in query("SELECT DISTINCT action FROM audit_log ORDER BY action")]
    return jsonify({"entries": rows, "actions": actions})
