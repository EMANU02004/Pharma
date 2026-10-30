"""Medicine catalogue, pharmacy list and medicine search (any logged-in user)."""
from flask import Blueprint, current_app, jsonify, request

from ..db import query
from ..errors import ApiError
from ..geo import SORT_KEYS, format_time, haversine_km, is_open
from ..security import login_required
from ..validation import as_float, as_int

bp = Blueprint("search", __name__, url_prefix="/api")


@bp.get("/medicines")
@login_required
def medicines():
    q = (request.args.get("q") or "").strip()
    like = f"%{q}%"
    rows = query(
        """SELECT medicine_id, brand_name, generic_name, strength_form, requires_prescription
           FROM medicines WHERE brand_name LIKE %s OR generic_name LIKE %s
           ORDER BY generic_name, brand_name LIMIT 60""",
        (like, like),
    )
    return jsonify(rows)


@bp.get("/pharmacies")
@login_required
def pharmacies():
    tz = current_app.config["TIMEZONE"]
    rows = query(
        "SELECT pharmacy_id, name, address, latitude, longitude, open_days, opens_at, closes_at "
        "FROM pharmacies WHERE is_active = TRUE ORDER BY name"
    )
    for r in rows:
        r["latitude"], r["longitude"] = float(r["latitude"]), float(r["longitude"])
        r["open_now"] = is_open(r["open_days"], r["opens_at"], r["closes_at"], tz=tz)
        r["opens_at"], r["closes_at"] = format_time(r["opens_at"]), format_time(r["closes_at"])
    return jsonify(rows)


@bp.get("/search/medicine")
@login_required
def search_medicine():
    """Find active pharmacies stocking a medicine (brand or generic name).

    Query params: q (required, 2+ chars), lat/lng (optional, enables distance),
    sort=distance|price|stock, in_stock=1, open_now=1, max_km, min_qty.
    """
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        raise ApiError("Type at least 2 characters to search", 422, {"q": "min 2 chars"})
    sort = request.args.get("sort", "distance")
    if sort not in SORT_KEYS:
        raise ApiError("sort must be distance, price or stock", 422)
    lat, lng = request.args.get("lat"), request.args.get("lng")
    origin = None
    if lat not in (None, "") and lng not in (None, ""):
        origin = (as_float(lat, "lat", -90, 90), as_float(lng, "lng", -180, 180))
    in_stock_only = request.args.get("in_stock", "1") == "1"
    open_now_only = request.args.get("open_now") == "1"
    max_km = as_float(request.args["max_km"], "max_km", 0.1, 500) if request.args.get("max_km") else None
    min_qty = as_int(request.args.get("min_qty") or 1, "min_qty", 1, 100000)

    like = f"%{q}%"
    rows = query(
        """SELECT ph.pharmacy_id, ph.name AS pharmacy_name, ph.address, ph.latitude, ph.longitude,
                  ph.open_days, ph.opens_at, ph.closes_at,
                  m.medicine_id, m.brand_name, m.generic_name, m.strength_form, m.requires_prescription,
                  s.quantity, s.price_kes, s.updated_at
           FROM item_stock s
           JOIN medicines m ON m.medicine_id = s.medicine_id
           JOIN pharmacies ph ON ph.pharmacy_id = s.pharmacy_id
           WHERE ph.is_active = TRUE AND (m.brand_name LIKE %s OR m.generic_name LIKE %s)""",
        (like, like),
    )
    tz = current_app.config["TIMEZONE"]
    results = []
    for r in rows:
        if in_stock_only and r["quantity"] < min_qty:
            continue
        r["latitude"], r["longitude"] = float(r["latitude"]), float(r["longitude"])
        r["price_kes"] = float(r["price_kes"])
        r["distance_km"] = (round(haversine_km(origin[0], origin[1], r["latitude"], r["longitude"]), 2)
                            if origin else None)
        if max_km is not None and r["distance_km"] is not None and r["distance_km"] > max_km:
            continue
        r["open_now"] = is_open(r["open_days"], r["opens_at"], r["closes_at"], tz=tz)
        if open_now_only and not r["open_now"]:
            continue
        r["opens_at"], r["closes_at"] = format_time(r["opens_at"]), format_time(r["closes_at"])
        r["stock_level"] = ("out" if r["quantity"] == 0 else
                            "low" if r["quantity"] < current_app.config["LOW_STOCK_THRESHOLD"] else "ok")
        results.append(r)
    results.sort(key=SORT_KEYS[sort])
    return jsonify({"query": q, "sort": sort, "count": len(results), "results": results})


@bp.get("/notifications")
@login_required
def notifications():
    from ..security import current_user
    rows = query(
        """SELECT notification_id, channel, subject, body, delivery_status, created_at, read_at
           FROM notifications WHERE user_id=%s ORDER BY created_at DESC, notification_id DESC LIMIT 50""",
        (current_user()["user_id"],),
    )
    return jsonify(rows)


@bp.post("/notifications/<int:notification_id>/read")
@login_required
def mark_read(notification_id):
    from ..db import commit, execute
    from ..security import current_user
    from ..rx import now_local
    execute("UPDATE notifications SET read_at=%s WHERE notification_id=%s AND user_id=%s AND read_at IS NULL",
            (now_local(), notification_id, current_user()["user_id"]))
    commit()
    return jsonify({"ok": True})
