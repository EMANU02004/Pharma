"""Verification and dispensing: stock consistency and single use."""
import threading

from conftest import DOCTOR, PATIENT, PHARMACIST, ensure_stock, new_prescription, share


def _ready(login, sql, qty1=100, qty9=100):
    ensure_stock(sql, 1, 1, qty1)
    ensure_stock(sql, 1, 9, qty9)
    rx = new_prescription(login(DOCTOR))
    share(login(PATIENT), rx["prescription_id"], pharmacy_id=1)
    return rx


def _qty(sql, med):
    return sql("SELECT quantity FROM item_stock WHERE pharmacy_id=1 AND medicine_id=%s", (med,))[0]["quantity"]


def test_verify_shows_items_stock_and_price(login, sql):
    rx = _ready(login, sql)
    data = login(PHARMACIST).post("/api/pharmacy/verify", json={"code": rx["code"].lower()}).get_json()
    assert data["can_dispense"] is True
    assert all(it["enough"] for it in data["items"])
    assert data["total_price_kes"] > 0


def test_dispense_lowers_stock_and_fills_prescription(login, sql):
    rx = _ready(login, sql)
    r = login(PHARMACIST).post("/api/pharmacy/dispense", json={"code": rx["code"]})
    assert r.status_code == 200 and r.get_json()["status"] == "filled"
    assert _qty(sql, 1) == 40 and _qty(sql, 9) == 70
    row = sql("SELECT status, filled_by_pharmacy_id FROM prescriptions WHERE prescription_id=%s",
              (rx["prescription_id"],))[0]
    assert row == {"status": "filled", "filled_by_pharmacy_id": 1}
    assert sql("SELECT COUNT(*) n FROM audit_log WHERE action='DISPENSE'")[0]["n"] == 1


def test_code_cannot_be_used_twice(login, sql):
    rx = _ready(login, sql)
    pharmacist = login(PHARMACIST)
    assert pharmacist.post("/api/pharmacy/dispense", json={"code": rx["code"]}).status_code == 200
    second = pharmacist.post("/api/pharmacy/dispense", json={"code": rx["code"]})
    assert second.status_code == 409
    assert "only be filled once" in second.get_json()["error"]
    assert _qty(sql, 1) == 40   # stock not deducted a second time
    # Re-sharing a filled prescription is also refused
    r = login(PATIENT).post(f"/api/patient/prescriptions/{rx['prescription_id']}/grants", json={"pharmacy_id": 2})
    assert r.status_code == 409


def test_insufficient_stock_changes_nothing(login, sql):
    rx = _ready(login, sql, qty1=100, qty9=10)   # item 9 needs 30
    r = login(PHARMACIST).post("/api/pharmacy/dispense", json={"code": rx["code"]})
    assert r.status_code == 409
    assert _qty(sql, 1) == 100 and _qty(sql, 9) == 10     # all-or-nothing: no partial deduction
    assert sql("SELECT status FROM prescriptions WHERE prescription_id=%s", (rx["prescription_id"],))[0]["status"] == "active"


def test_expired_and_cancelled_prescriptions_cannot_be_dispensed(login, sql):
    rx = _ready(login, sql)
    sql("UPDATE prescriptions SET issue_date=CURDATE() - INTERVAL 40 DAY, expiry_date=CURDATE() - INTERVAL 1 DAY "
        "WHERE prescription_id=%s", (rx["prescription_id"],))
    r = login(PHARMACIST).post("/api/pharmacy/dispense", json={"code": rx["code"]})
    assert r.status_code == 409 and "expired" in r.get_json()["error"]

    rx2 = _ready(login, sql)
    login(DOCTOR).post(f"/api/doctor/prescriptions/{rx2['prescription_id']}/cancel")
    r = login(PHARMACIST).post("/api/pharmacy/dispense", json={"code": rx2["code"]})
    assert r.status_code == 409 and "cancelled" in r.get_json()["error"]


def test_code_guessing_is_rate_limited(login):
    pharmacist = login(PHARMACIST)
    for _ in range(10):
        assert pharmacist.post("/api/pharmacy/verify", json={"code": "ZZZZ-ZZZZ"}).status_code == 404
    assert pharmacist.post("/api/pharmacy/verify", json={"code": "ZZZZ-ZZZZ"}).status_code == 429


def test_concurrent_dispense_fills_exactly_once(app, login, sql):
    rx = _ready(login, sql)
    clients = [login(PHARMACIST), login(PHARMACIST)]
    results = []

    def go(c):
        results.append(c.post("/api/pharmacy/dispense", json={"code": rx["code"]}).status_code)

    threads = [threading.Thread(target=go, args=(c,)) for c in clients]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [200, 409]
    assert _qty(sql, 1) == 40
