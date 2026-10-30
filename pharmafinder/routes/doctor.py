"""Doctor endpoints: find patients, issue and cancel prescriptions."""
from datetime import timedelta

import pymysql
from flask import Blueprint, current_app, jsonify, request

from ..audit import log_action
from ..db import execute, query, query_one, transaction
from ..errors import ApiError
from ..notify import notify
from ..rx import expire_overdue, generate_code, load_prescriptions, today_local
from ..security import current_user, roles_required
from ..validation import as_int, clean_str, json_body

bp = Blueprint("doctor", __name__, url_prefix="/api/doctor")


@bp.get("/patients")
@roles_required("doctor")
def search_patients():
    q = (request.args.get("q") or "").strip()
    like = f"%{q}%"
    rows = query(
        """SELECT pt.patient_id, u.full_name, u.email, pt.date_of_birth, pt.sub_county
           FROM patients pt JOIN users u ON u.user_id = pt.user_id
           WHERE u.is_active = TRUE AND (u.full_name LIKE %s OR u.email LIKE %s)
           ORDER BY u.full_name LIMIT 25""",
        (like, like),
    )
    return jsonify(rows)


def _validate_items(raw_items):
    if not isinstance(raw_items, list) or not raw_items:
        raise ApiError("A prescription needs at least one medicine", 422, {"items": "required"})
    if len(raw_items) > 20:
        raise ApiError("A prescription can have at most 20 medicines", 422)
    items, seen = [], set()
    for i, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, dict):
            raise ApiError(f"Item {i} is invalid", 422)
        medicine_id = as_int(raw.get("medicine_id"), f"items[{i}].medicine_id", 1)
        if medicine_id in seen:
            raise ApiError(f"Item {i}: the same medicine is listed twice", 422)
        seen.add(medicine_id)
        items.append({
            "medicine_id": medicine_id,
            "dose": clean_str(raw.get("dose"), f"items[{i}].dose", 60),
            "frequency": clean_str(raw.get("frequency"), f"items[{i}].frequency", 60),
            "duration_days": as_int(raw.get("duration_days"), f"items[{i}].duration_days", 1, 365),
            "quantity": as_int(raw.get("quantity"), f"items[{i}].quantity", 1, 1000),
        })
    marks = ",".join(["%s"] * len(seen))
    found = query(f"SELECT medicine_id FROM medicines WHERE medicine_id IN ({marks})", tuple(seen))
    if len(found) != len(seen):
        raise ApiError("One or more medicines do not exist in the catalogue", 422)
    return items


@bp.post("/prescriptions")
@roles_required("doctor")
def create_prescription():
    """Create a prescription; every mandatory field is validated here, not in the browser."""
    user = current_user()
    data = json_body()
    cfg = current_app.config

    patient_id = as_int(data.get("patient_id"), "patient_id", 1)
    patient = query_one(
        """SELECT pt.patient_id, u.user_id, u.full_name, u.email FROM patients pt
           JOIN users u ON u.user_id = pt.user_id WHERE pt.patient_id=%s AND u.is_active=TRUE""",
        (patient_id,),
    )
    if not patient:
        raise ApiError("Patient not found", 404)

    valid_days = as_int(data.get("valid_days", cfg["PRESCRIPTION_DEFAULT_VALID_DAYS"]),
                        "valid_days", 1, cfg["PRESCRIPTION_MAX_VALID_DAYS"])
    notes = clean_str(data.get("notes"), "notes", 500, required=False)
    items = _validate_items(data.get("items"))

    issue = today_local()
    expiry = issue + timedelta(days=valid_days)

    with transaction():
        for _attempt in range(5):  # retry on the (very unlikely) code collision
            code = generate_code()
            try:
                rx_id = execute(
                    """INSERT INTO prescriptions (code, patient_id, doctor_id, issue_date, expiry_date, notes)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (code, patient_id, user["doctor_id"], issue, expiry, notes),
                )
                break
            except pymysql.err.IntegrityError as exc:
                if "uq_prescriptions_code" not in str(exc):
                    raise
        else:
            raise ApiError("Could not generate a unique code, please retry", 503)

        for it in items:
            execute(
                """INSERT INTO prescription_items
                   (prescription_id, medicine_id, dose, frequency, duration_days, quantity)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (rx_id, it["medicine_id"], it["dose"], it["frequency"], it["duration_days"], it["quantity"]),
            )
        log_action(user["user_id"], "CREATE_PRESCRIPTION", "prescription", rx_id,
                   f"patient_id={patient_id}; items={len(items)}")
        delivery = notify(
            patient["user_id"], patient["email"],
            "New prescription issued",
            f"Dr. {user['full_name']} issued you a prescription with {len(items)} medicine(s). "
            f"Code: {code}. Valid until {expiry.isoformat()}. "
            "Open PharmaFinder to find pharmacies that have it in stock.",
        )

    rx = load_prescriptions("p.prescription_id=%s", (rx_id,))[0]
    rx["notification"] = delivery
    return jsonify(rx), 201


@bp.get("/prescriptions")
@roles_required("doctor")
def my_prescriptions():
    expire_overdue()
    return jsonify(load_prescriptions("p.doctor_id=%s", (current_user()["doctor_id"],)))


@bp.post("/prescriptions/<int:rx_id>/cancel")
@roles_required("doctor")
def cancel_prescription(rx_id):
    user = current_user()
    expire_overdue()
    with transaction():
        rx = query_one(
            "SELECT prescription_id, doctor_id, status FROM prescriptions WHERE prescription_id=%s FOR UPDATE",
            (rx_id,),
        )
        if not rx or rx["doctor_id"] != user["doctor_id"]:
            raise ApiError("Prescription not found", 404)
        if rx["status"] != "active":
            raise ApiError(f"Only active prescriptions can be cancelled (this one is {rx['status']})", 409)
        execute("UPDATE prescriptions SET status='cancelled' WHERE prescription_id=%s", (rx_id,))
        log_action(user["user_id"], "CANCEL_PRESCRIPTION", "prescription", rx_id)
    return jsonify({"prescription_id": rx_id, "status": "cancelled"})
