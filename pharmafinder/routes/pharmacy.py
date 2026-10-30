"""Pharmacist endpoints: stock management, code verification, dispensing."""
from flask import Blueprint, current_app, jsonify

from ..audit import log_action
from ..db import commit, execute, get_db, query, query_one, transaction
from ..errors import ApiError
from ..notify import notify
from ..rx import active_grant, expire_overdue, load_prescriptions, normalise_code, now_local, today_local
from ..security import current_user, recent_failures, roles_required
from ..validation import as_int, as_price, clean_str, json_body

bp = Blueprint("pharmacy", __name__, url_prefix="/api/pharmacy")

NOT_SHARED = ("No prescription with this code has been shared with your pharmacy. "
              "Ask the patient to share it from their Health Passport.")


def _pharmacy_id():
    pid = current_user().get("pharmacy_id")
    if not pid:
        raise ApiError("Your account is not linked to a pharmacy", 403)
    return pid


# ---------------------------------------------------------------- stock ----

def _stock_rows(pharmacy_id):
    threshold = current_app.config["LOW_STOCK_THRESHOLD"]
    rows = query(
        """SELECT s.stock_id, s.medicine_id, m.brand_name, m.generic_name, m.strength_form,
                  m.requires_prescription, s.quantity, s.price_kes, s.updated_at
           FROM item_stock s JOIN medicines m ON m.medicine_id = s.medicine_id
           WHERE s.pharmacy_id=%s ORDER BY m.generic_name, m.brand_name""",
        (pharmacy_id,),
    )
    for r in rows:
        r["price_kes"] = float(r["price_kes"])
        r["stock_level"] = "out" if r["quantity"] == 0 else "low" if r["quantity"] < threshold else "ok"
    return rows


@bp.get("/stock")
@roles_required("pharmacist")
def list_stock():
    pid = _pharmacy_id()
    rows = _stock_rows(pid)
    last = max((r["updated_at"] for r in rows), default=None)
    return jsonify({
        "pharmacy_id": pid, "last_updated": last, "items": rows,
        "summary": {
            "total": len(rows),
            "low": sum(r["stock_level"] == "low" for r in rows),
            "out": sum(r["stock_level"] == "out" for r in rows),
        },
    })


@bp.post("/stock")
@roles_required("pharmacist")
def add_stock():
    user = current_user()
    pid = _pharmacy_id()
    data = json_body()
    medicine_id = as_int(data.get("medicine_id"), "medicine_id", 1)
    quantity = as_int(data.get("quantity"), "quantity", 0, 100000)
    price = as_price(data.get("price_kes"))
    if not query_one("SELECT 1 FROM medicines WHERE medicine_id=%s", (medicine_id,)):
        raise ApiError("Medicine not found in the catalogue", 404)
    if query_one("SELECT 1 FROM item_stock WHERE pharmacy_id=%s AND medicine_id=%s", (pid, medicine_id)):
        raise ApiError("This medicine is already in your stock. Update it instead.", 409)
    with transaction():
        stock_id = execute(
            "INSERT INTO item_stock (pharmacy_id, medicine_id, price_kes, quantity, updated_at) "
            "VALUES (%s,%s,%s,%s,%s)",
            (pid, medicine_id, price, quantity, now_local()),
        )
        log_action(user["user_id"], "STOCK_ADD", "item_stock", stock_id,
                   f"medicine_id={medicine_id}; qty={quantity}; price={price}")
    return jsonify({"stock_id": stock_id}), 201


@bp.patch("/stock/<int:stock_id>")
@roles_required("pharmacist")
def update_stock(stock_id):
    user = current_user()
    pid = _pharmacy_id()
    data = json_body()
    if "quantity" not in data and "price_kes" not in data:
        raise ApiError("Send quantity and/or price_kes", 422)
    with transaction():
        row = query_one("SELECT stock_id, pharmacy_id, quantity, price_kes FROM item_stock "
                        "WHERE stock_id=%s FOR UPDATE", (stock_id,))
        if not row or row["pharmacy_id"] != pid:  # never touch another pharmacy's stock
            raise ApiError("Stock item not found", 404)
        quantity = as_int(data["quantity"], "quantity", 0, 100000) if "quantity" in data else row["quantity"]
        price = as_price(data["price_kes"]) if "price_kes" in data else float(row["price_kes"])
        execute("UPDATE item_stock SET quantity=%s, price_kes=%s, updated_at=%s WHERE stock_id=%s",
                (quantity, price, now_local(), stock_id))
        log_action(user["user_id"], "STOCK_UPDATE", "item_stock", stock_id,
                   f"qty {row['quantity']}->{quantity}; price {float(row['price_kes'])}->{price}")
    return jsonify({"stock_id": stock_id, "quantity": quantity, "price_kes": price})


@bp.post("/medicines")
@roles_required("pharmacist")
def add_medicine():
    """Add a medicine that is missing from the shared catalogue."""
    user = current_user()
    data = json_body()
    brand = clean_str(data.get("brand_name"), "brand_name", 120)
    generic = clean_str(data.get("generic_name"), "generic_name", 120)
    form = clean_str(data.get("strength_form"), "strength_form", 80)
    requires_rx = bool(data.get("requires_prescription", True))
    if query_one("SELECT 1 FROM medicines WHERE brand_name=%s AND strength_form=%s", (brand, form)):
        raise ApiError("This medicine is already in the catalogue", 409)
    with transaction():
        mid = execute("INSERT INTO medicines (brand_name, generic_name, strength_form, requires_prescription) "
                      "VALUES (%s,%s,%s,%s)", (brand, generic, form, requires_rx))
        log_action(user["user_id"], "MEDICINE_ADD", "medicine", mid, brand)
    return jsonify({"medicine_id": mid}), 201


# ------------------------------------------------------- verify/dispense ----

def _check_rate_limit(user_id):
    if recent_failures("VERIFY_FAILED", user_id=user_id) >= current_app.config["MAX_FAILED_CODE_CHECKS"]:
        raise ApiError("Too many incorrect codes. Try again in 15 minutes.", 429)


def _fail(user_id, code_text):
    log_action(user_id, "VERIFY_FAILED", "prescription", None, code_text[:20])
    commit()
    raise ApiError(NOT_SHARED, 404)


def _state_error(rx):
    if rx["status"] == "filled":
        when = rx["filled_at"].strftime("%Y-%m-%d %H:%M") if rx.get("filled_at") else "earlier"
        return ApiError(f"Already dispensed on {when}. A prescription can only be filled once.", 409)
    if rx["status"] == "expired" or rx["expiry_date"] < today_local():
        return ApiError(f"This prescription expired on {rx['expiry_date']}.", 409)
    if rx["status"] == "cancelled":
        return ApiError("The doctor cancelled this prescription.", 409)
    return None


@bp.post("/verify")
@roles_required("pharmacist")
def verify():
    """Check a prescription code. Only works if the patient shared it with this pharmacy."""
    user = current_user()
    pid = _pharmacy_id()
    _check_rate_limit(user["user_id"])
    raw = str(json_body().get("code") or "")
    code = normalise_code(raw)
    if not code:
        _fail(user["user_id"], raw)
    expire_overdue()
    rows = load_prescriptions("p.code=%s", (code,))
    # Access needs a live grant - or this pharmacy is the one that already filled it
    if not rows or (not active_grant(rows[0]["prescription_id"], pid)
                    and rows[0]["filled_by_pharmacy_id"] != pid):
        _fail(user["user_id"], code)
    rx = rows[0]

    stock = {s["medicine_id"]: s for s in query(
        "SELECT medicine_id, quantity, price_kes FROM item_stock WHERE pharmacy_id=%s", (pid,))}
    total = 0.0
    for it in rx["items"]:
        s = stock.get(it["medicine_id"])
        it["in_stock"] = s["quantity"] if s else 0
        it["unit_price_kes"] = float(s["price_kes"]) if s else None
        it["enough"] = bool(s and s["quantity"] >= it["quantity"])
        if it["enough"]:
            total += float(s["price_kes"]) * it["quantity"]
    err = _state_error(rx)
    rx["can_dispense"] = err is None and all(it["enough"] for it in rx["items"])
    rx["blocked_reason"] = err.message if err else (
        None if rx["can_dispense"] else "Not enough stock for every item")
    rx["total_price_kes"] = round(total, 2)
    log_action(user["user_id"], "VERIFY_PRESCRIPTION", "prescription", rx["prescription_id"])
    commit()
    return jsonify(rx)


@bp.post("/dispense")
@roles_required("pharmacist")
def dispense():
    """Dispense every item, lower stock and mark the prescription filled - all in one transaction.

    Row locks (SELECT ... FOR UPDATE) on the prescription and stock rows mean two
    pharmacists cannot fill the same prescription or oversell the same stock.
    """
    user = current_user()
    pid = _pharmacy_id()
    _check_rate_limit(user["user_id"])
    raw = str(json_body().get("code") or "")
    code = normalise_code(raw)
    if not code:
        _fail(user["user_id"], raw)
    expire_overdue()

    conn = get_db()
    try:
        rx = query_one(
            "SELECT prescription_id, patient_id, status, expiry_date, filled_at, filled_by_pharmacy_id "
            "FROM prescriptions WHERE code=%s FOR UPDATE", (code,))
        if not rx or (not active_grant(rx["prescription_id"], pid) and rx["filled_by_pharmacy_id"] != pid):
            conn.rollback()
            _fail(user["user_id"], code)
        err = _state_error(rx)
        if err:
            raise err

        items = query("SELECT medicine_id, quantity FROM prescription_items WHERE prescription_id=%s",
                      (rx["prescription_id"],))
        marks = ",".join(["%s"] * len(items))
        stock = {s["medicine_id"]: s for s in query(
            f"SELECT stock_id, medicine_id, quantity FROM item_stock "
            f"WHERE pharmacy_id=%s AND medicine_id IN ({marks}) FOR UPDATE",
            (pid, *[i["medicine_id"] for i in items]))}
        short = [i["medicine_id"] for i in items
                 if i["medicine_id"] not in stock or stock[i["medicine_id"]]["quantity"] < i["quantity"]]
        if short:
            raise ApiError("Not enough stock to dispense every item", 409, {"medicine_ids": short})

        now = now_local()
        with conn.cursor() as cur:
            for i in items:
                cur.execute(
                    "UPDATE item_stock SET quantity = quantity - %s, updated_at=%s "
                    "WHERE stock_id=%s AND quantity >= %s",
                    (i["quantity"], now, stock[i["medicine_id"]]["stock_id"], i["quantity"]))
                if cur.rowcount != 1:
                    raise ApiError("Stock changed while dispensing; please retry", 409)
            cur.execute(
                "UPDATE prescriptions SET status='filled', filled_at=%s, filled_by_pharmacy_id=%s "
                "WHERE prescription_id=%s AND status='active'",
                (now, pid, rx["prescription_id"]))
            if cur.rowcount != 1:
                raise ApiError("This prescription was already filled", 409)
            # The prescription is used up: close every open access grant
            cur.execute("UPDATE grant_access SET revoked_at=%s WHERE prescription_id=%s "
                        "AND revoked_at IS NULL AND expires_at > %s", (now, rx["prescription_id"], now))
        log_action(user["user_id"], "DISPENSE", "prescription", rx["prescription_id"],
                   f"pharmacy_id={pid}; items={len(items)}")
        patient = query_one("SELECT u.user_id, u.email FROM patients p JOIN users u ON u.user_id=p.user_id "
                            "WHERE p.patient_id=%s", (rx["patient_id"],))
        pharmacy = query_one("SELECT name FROM pharmacies WHERE pharmacy_id=%s", (pid,))
        notify(patient["user_id"], patient["email"], "Prescription collected",
               f"Your prescription {code} was dispensed at {pharmacy['name']}. "
               "It is now marked as filled and cannot be used again.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return jsonify({"prescription_id": rx["prescription_id"], "code": code, "status": "filled",
                    "filled_at": now, "items_dispensed": len(items)})


@bp.get("/shared")
@roles_required("pharmacist")
def shared_with_me():
    """Prescriptions that patients currently share with this pharmacy."""
    pid = _pharmacy_id()
    expire_overdue()
    now = now_local()
    rows = query(
        """SELECT p.prescription_id, p.code, p.status, p.issue_date, p.expiry_date,
                  u.full_name AS patient_name, g.expires_at AS access_expires_at,
                  (SELECT COUNT(*) FROM prescription_items i WHERE i.prescription_id=p.prescription_id) AS item_count
           FROM grant_access g
           JOIN prescriptions p ON p.prescription_id = g.prescription_id
           JOIN patients pt ON pt.patient_id = p.patient_id
           JOIN users u ON u.user_id = pt.user_id
           WHERE g.pharmacy_id=%s AND g.revoked_at IS NULL AND g.granted_at <= %s AND g.expires_at > %s
           ORDER BY g.granted_at DESC""",
        (pid, now, now),
    )
    return jsonify(rows)


@bp.get("/dispensed")
@roles_required("pharmacist")
def dispensed_history():
    pid = _pharmacy_id()
    return jsonify(query(
        """SELECT p.prescription_id, p.code, p.filled_at, u.full_name AS patient_name,
                  (SELECT COUNT(*) FROM prescription_items i WHERE i.prescription_id=p.prescription_id) AS item_count
           FROM prescriptions p JOIN patients pt ON pt.patient_id=p.patient_id
           JOIN users u ON u.user_id=pt.user_id
           WHERE p.filled_by_pharmacy_id=%s ORDER BY p.filled_at DESC LIMIT 50""",
        (pid,),
    ))
