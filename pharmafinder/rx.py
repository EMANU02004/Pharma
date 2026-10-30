"""Shared prescription logic: codes, expiry, loading, and access grants."""
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import current_app

from .db import commit, execute, query, query_one

# No 0/O, 1/I/L - avoids misreading the code at the counter.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def now_local():
    """Naive datetime in Kenya time; all app timestamps use this clock."""
    tz = ZoneInfo(current_app.config["TIMEZONE"])
    return datetime.now(tz).replace(tzinfo=None, microsecond=0)


def today_local():
    return now_local().date()


def generate_code():
    """Random, unguessable code like 'K7QM-2XPA' (31^8 ~ 8.5e11 possibilities)."""
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def normalise_code(code):
    code = "".join(ch for ch in str(code or "").upper() if ch.isalnum())
    if len(code) != 8 or any(ch not in CODE_ALPHABET for ch in code):
        return None
    return f"{code[:4]}-{code[4:]}"


def expire_overdue():
    """Mark active prescriptions past their expiry date as expired.

    Runs at the start of every prescription read, so expiry never depends on a
    background job (which serverless hosts such as Vercel do not provide).
    """
    execute(
        "UPDATE prescriptions SET status='expired' WHERE status='active' AND expiry_date < %s",
        (today_local(),),
    )
    commit()


PRESCRIPTION_SELECT = """
SELECT p.prescription_id, p.code, p.issue_date, p.expiry_date, p.status, p.notes,
       p.filled_at, p.filled_by_pharmacy_id, fp.name AS filled_by_pharmacy,
       p.patient_id, pu.full_name AS patient_name, pt.date_of_birth AS patient_dob,
       p.doctor_id, du.full_name AS doctor_name, d.facility AS doctor_facility,
       d.license_number AS doctor_license
FROM prescriptions p
JOIN patients pt ON pt.patient_id = p.patient_id
JOIN users pu ON pu.user_id = pt.user_id
JOIN doctors d ON d.doctor_id = p.doctor_id
JOIN users du ON du.user_id = d.user_id
LEFT JOIN pharmacies fp ON fp.pharmacy_id = p.filled_by_pharmacy_id
"""


def load_items(prescription_ids):
    if not prescription_ids:
        return {}
    marks = ",".join(["%s"] * len(prescription_ids))
    rows = query(
        f"""SELECT i.item_id, i.prescription_id, i.medicine_id, m.brand_name, m.generic_name,
                   m.strength_form, i.dose, i.frequency, i.duration_days, i.quantity
            FROM prescription_items i JOIN medicines m ON m.medicine_id = i.medicine_id
            WHERE i.prescription_id IN ({marks}) ORDER BY i.item_id""",
        tuple(prescription_ids),
    )
    grouped = {pid: [] for pid in prescription_ids}
    for r in rows:
        grouped[r["prescription_id"]].append(r)
    return grouped


def load_prescriptions(where_sql, params):
    rows = query(PRESCRIPTION_SELECT + " WHERE " + where_sql + " ORDER BY p.issue_date DESC, p.prescription_id DESC", params)
    items = load_items([r["prescription_id"] for r in rows])
    for r in rows:
        r["items"] = items.get(r["prescription_id"], [])
    return rows


def active_grant(prescription_id, pharmacy_id):
    now = now_local()
    return query_one(
        """SELECT grant_id, granted_at, expires_at FROM grant_access
           WHERE prescription_id=%s AND pharmacy_id=%s AND revoked_at IS NULL
             AND granted_at <= %s AND expires_at > %s
           ORDER BY expires_at DESC LIMIT 1""",
        (prescription_id, pharmacy_id, now, now),
    )
