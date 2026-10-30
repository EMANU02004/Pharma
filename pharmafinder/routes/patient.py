"""Patient endpoints: Health Passport, sharing/revoking access, prescription-based search."""
from datetime import timedelta

from flask import Blueprint, current_app, jsonify, request

from ..audit import log_action
from ..db import execute, query, query_one, transaction
from ..errors import ApiError
from ..geo import format_time, haversine_km, is_open, rank_prescription_matches
from ..rx import expire_overdue, load_prescriptions, now_local
from ..security import current_user, roles_required
from ..validation import as_float, as_int, json_body

bp = Blueprint("patient", __name__, url_prefix="/api/patient")


def _own_prescription(rx_id):
    """Return the prescription only if it belongs to the logged-in patient (else 404)."""
    rows = load_prescriptions("p.prescription_id=%s AND p.patient_id=%s",
                              (rx_id, current_user()["patient_id"]))
    if not rows:
        raise ApiError("Prescription not found", 404)
    return rows[0]


def _grants_for(where, params):
    now = now_local()
    rows = query(
        f"""SELECT g.grant_id, g.prescription_id, p.code, g.pharmacy_id, ph.name AS pharmacy_name,
                   g.granted_at, g.expires_at, g.revoked_at
            FROM grant_access g
            JOIN prescriptions p ON p.prescription_id = g.prescription_id
            JOIN pharmacies ph ON ph.pharmacy_id = g.pharmacy_id
            WHERE {where} ORDER BY g.granted_at DESC""",
        params,
    )
    for g in rows:
        if g["revoked_at"]:
            g["state"] = "revoked"
        elif g["expires_at"] <= now:
            g["state"] = "expired"
        else:
            g["state"] = "active"
    return rows


@bp.get("/prescriptions")
@roles_required("patient")
def list_prescriptions():
    expire_overdue()
    rows = load_prescriptions("p.patient_id=%s", (current_user()["patient_id"],))
    grants = _grants_for("p.patient_id=%s", (current_user()["patient_id"],))
    for rx in rows:
        rx["grants"] = [g for g in grants if g["prescription_id"] == rx["prescription_id"]]
    return jsonify(rows)


@bp.get("/prescriptions/<int:rx_id>")
@roles_required("patient")
def get_prescription(rx_id):
    expire_overdue()
    rx = _own_prescription(rx_id)
    rx["grants"] = _grants_for("g.prescription_id=%s", (rx_id,))
    return jsonify(rx)


@bp.post("/prescriptions/<int:rx_id>/grants")
@roles_required("patient")
def grant_access(rx_id):
    """Let one pharmacy open this prescription for a limited number of hours."""
    user = current_user()
    cfg = current_app.config
    data = json_body()
    expire_overdue()
    rx = _own_prescription(rx_id)
    if rx["status"] != "active":
        raise ApiError(f"Only active prescriptions can be shared (this one is {rx['status']})", 409)

    pharmacy_id = as_int(data.get("pharmacy_id"), "pharmacy_id", 1)
    hours = as_int(data.get("hours", cfg["GRANT_DEFAULT_HOURS"]), "hours", 1, cfg["GRANT_MAX_HOURS"])
    pharmacy = query_one("SELECT pharmacy_id, name FROM pharmacies WHERE pharmacy_id=%s AND is_active=TRUE",
                         (pharmacy_id,))
    if not pharmacy:
        raise ApiError("Pharmacy not found", 404)

    now = now_local()
    expires = now + timedelta(hours=hours)
    with transaction():
        # One live grant per pharmacy: end any existing one before creating the new window
        execute(
            """UPDATE grant_access SET revoked_at=%s
               WHERE prescription_id=%s AND pharmacy_id=%s AND revoked_at IS NULL AND expires_at > %s""",
            (now, rx_id, pharmacy_id, now),
        )
        grant_id = execute(
            "INSERT INTO grant_access (prescription_id, pharmacy_id, granted_at, expires_at) VALUES (%s,%s,%s,%s)",
            (rx_id, pharmacy_id, now, expires),
        )
        log_action(user["user_id"], "GRANT_ACCESS", "prescription", rx_id,
                   f"pharmacy_id={pharmacy_id}; hours={hours}")
    return jsonify({"grant_id": grant_id, "prescription_id": rx_id, "pharmacy_id": pharmacy_id,
                    "pharmacy_name": pharmacy["name"], "granted_at": now, "expires_at": expires,
                    "state": "active"}), 201


@bp.get("/grants")
@roles_required("patient")
def list_grants():
    return jsonify(_grants_for("p.patient_id=%s", (current_user()["patient_id"],)))


@bp.post("/grants/<int:grant_id>/revoke")
@roles_required("patient")
def revoke_grant(grant_id):
    user = current_user()
    now = now_local()
    with transaction():
        grant = query_one(
            """SELECT g.grant_id, g.prescription_id, g.revoked_at, p.patient_id
               FROM grant_access g JOIN prescriptions p ON p.prescription_id = g.prescription_id
               WHERE g.grant_id=%s FOR UPDATE""",
            (grant_id,),
        )
        if not grant or grant["patient_id"] != user["patient_id"]:
            raise ApiError("Access grant not found", 404)
        if grant["revoked_at"]:
            raise ApiError("This access has already been revoked", 409)
        execute("UPDATE grant_access SET revoked_at=%s WHERE grant_id=%s", (now, grant_id))
        log_action(user["user_id"], "REVOKE_ACCESS", "prescription", grant["prescription_id"],
                   f"grant_id={grant_id}")
    return jsonify({"grant_id": grant_id, "state": "revoked", "revoked_at": now})


@bp.get("/prescriptions/<int:rx_id>/pharmacies")
@roles_required("patient")
def pharmacies_for_prescription(rx_id):
    """Rank pharmacies by how much of this prescription they can supply, then distance."""
    expire_overdue()
    rx = _own_prescription(rx_id)
    lat = request.args.get("lat")
    lng = request.args.get("lng")
    origin = None
    if lat not in (None, "") and lng not in (None, ""):
        origin = (as_float(lat, "lat", -90, 90), as_float(lng, "lng", -180, 180))

    needed = {it["medicine_id"]: it["quantity"] for it in rx["items"]}
    marks = ",".join(["%s"] * len(needed))
    stock = query(
        f"""SELECT s.pharmacy_id, s.medicine_id, s.quantity, s.price_kes, s.updated_at
            FROM item_stock s JOIN pharmacies ph ON ph.pharmacy_id = s.pharmacy_id
            WHERE ph.is_active = TRUE AND s.medicine_id IN ({marks})""",
        tuple(needed),
    )
    pharmacies = query(
        "SELECT pharmacy_id, name, address, latitude, longitude, open_days, opens_at, closes_at "
        "FROM pharmacies WHERE is_active = TRUE"
    )
    tz = current_app.config["TIMEZONE"]
    results = []
    for ph in pharmacies:
        lines = []
        total = 0.0
        available = 0
        for it in rx["items"]:
            s = next((s for s in stock if s["pharmacy_id"] == ph["pharmacy_id"]
                      and s["medicine_id"] == it["medicine_id"]), None)
            enough = bool(s and s["quantity"] >= it["quantity"])
            if enough:
                available += 1
                total += float(s["price_kes"]) * it["quantity"]
            lines.append({
                "medicine_id": it["medicine_id"], "brand_name": it["brand_name"],
                "needed": it["quantity"], "in_stock": s["quantity"] if s else 0,
                "unit_price_kes": float(s["price_kes"]) if s else None,
                "enough": enough, "updated_at": s["updated_at"] if s else None,
            })
        lat_f, lng_f = float(ph["latitude"]), float(ph["longitude"])
        results.append({
            "pharmacy_id": ph["pharmacy_id"], "name": ph["name"], "address": ph["address"],
            "latitude": lat_f, "longitude": lng_f,
            "distance_km": round(haversine_km(origin[0], origin[1], lat_f, lng_f), 2) if origin else None,
            "open_days": ph["open_days"], "opens_at": format_time(ph["opens_at"]),
            "closes_at": format_time(ph["closes_at"]),
            "open_now": is_open(ph["open_days"], ph["opens_at"], ph["closes_at"], tz=tz),
            "items_available": available, "items_needed": len(needed),
            "can_fill_all": available == len(needed),
            "total_price_kes": round(total, 2), "lines": lines,
        })
    return jsonify({"prescription_id": rx_id, "code": rx["code"], "status": rx["status"],
                    "results": rank_prescription_matches(results, len(needed))})
