"""Stock management and medicine/pharmacy search."""
from conftest import ADMIN, DOCTOR, PATIENT, PHARMACIST, PHARMACIST2, ensure_stock, new_prescription

ELDORET_CBD = "lat=0.5143&lng=35.2698"


def _my_stock_line(pharmacist, medicine_id):
    items = pharmacist.get("/api/pharmacy/stock").get_json()["items"]
    return next((i for i in items if i["medicine_id"] == medicine_id), None)


def test_pharmacist_sees_own_stock_with_levels(login):
    data = login(PHARMACIST).get("/api/pharmacy/stock").get_json()
    assert data["pharmacy_id"] == 1
    assert data["summary"]["total"] == len(data["items"]) > 0
    assert data["last_updated"] is not None
    assert {i["stock_level"] for i in data["items"]} <= {"ok", "low", "out"}


def test_update_stock_and_price_is_saved_and_audited(login, sql):
    pharmacist = login(PHARMACIST)
    line = pharmacist.get("/api/pharmacy/stock").get_json()["items"][0]
    r = pharmacist.patch(f"/api/pharmacy/stock/{line['stock_id']}", json={"quantity": 77, "price_kes": 42.5})
    assert r.status_code == 200
    row = sql("SELECT quantity, price_kes FROM item_stock WHERE stock_id=%s", (line["stock_id"],))[0]
    assert row["quantity"] == 77 and float(row["price_kes"]) == 42.5
    assert sql("SELECT COUNT(*) n FROM audit_log WHERE action='STOCK_UPDATE'")[0]["n"] == 1


def test_negative_stock_and_invalid_price_rejected(login):
    pharmacist = login(PHARMACIST)
    line = pharmacist.get("/api/pharmacy/stock").get_json()["items"][0]
    assert pharmacist.patch(f"/api/pharmacy/stock/{line['stock_id']}", json={"quantity": -1}).status_code == 422
    assert pharmacist.patch(f"/api/pharmacy/stock/{line['stock_id']}", json={"price_kes": 0}).status_code == 422
    assert pharmacist.patch(f"/api/pharmacy/stock/{line['stock_id']}", json={"price_kes": "abc"}).status_code == 422


def test_pharmacist_cannot_edit_another_pharmacys_stock(login, sql):
    other_line = sql("SELECT stock_id FROM item_stock WHERE pharmacy_id=2 LIMIT 1")[0]["stock_id"]
    r = login(PHARMACIST).patch(f"/api/pharmacy/stock/{other_line}", json={"quantity": 1})
    assert r.status_code == 404


def test_add_new_medicine_and_stock_line(login):
    pharmacist = login(PHARMACIST)
    r = pharmacist.post("/api/pharmacy/medicines", json={"brand_name": "Testocin", "generic_name": "Testamol",
                                                         "strength_form": "10 mg tablet"})
    assert r.status_code == 201
    mid = r.get_json()["medicine_id"]
    assert pharmacist.post("/api/pharmacy/stock", json={"medicine_id": mid, "quantity": 50, "price_kes": 12}).status_code == 201
    assert pharmacist.post("/api/pharmacy/stock", json={"medicine_id": mid, "quantity": 5, "price_kes": 12}).status_code == 409
    assert _my_stock_line(pharmacist, mid)["quantity"] == 50


def test_search_by_generic_name_returns_only_in_stock_sorted_by_distance(login, sql):
    ensure_stock(sql, 1, 1, 100)
    ensure_stock(sql, 2, 1, 0)
    ensure_stock(sql, 3, 1, 40)
    r = login(PATIENT).get(f"/api/search/medicine?q=metformin&{ELDORET_CBD}")
    data = r.get_json()
    assert r.status_code == 200 and data["count"] > 0
    assert all(row["quantity"] >= 1 for row in data["results"])
    assert all("metformin" in row["generic_name"].lower() for row in data["results"])
    distances = [row["distance_km"] for row in data["results"]]
    assert distances == sorted(distances)
    assert not any(row["pharmacy_id"] == 2 and row["medicine_id"] == 1 for row in data["results"])


def test_search_sort_by_price(login):
    data = login(PATIENT).get(f"/api/search/medicine?q=paracetamol&sort=price&{ELDORET_CBD}").get_json()
    prices = [row["price_kes"] for row in data["results"]]
    assert prices == sorted(prices)


def test_search_matches_stock_table_exactly(login, sql):
    """Every pharmacy with stock > 0 for the medicine appears; no others do."""
    expected = {r["pharmacy_id"] for r in sql(
        "SELECT s.pharmacy_id FROM item_stock s JOIN medicines m ON m.medicine_id=s.medicine_id "
        "WHERE m.generic_name='Amlodipine' AND s.quantity > 0")}
    got = {r["pharmacy_id"] for r in login(PATIENT).get("/api/search/medicine?q=amlodipine").get_json()["results"]}
    assert got == expected


def test_search_input_validation(login):
    patient = login(PATIENT)
    assert patient.get("/api/search/medicine?q=a").status_code == 422
    assert patient.get("/api/search/medicine?q=para&lat=999&lng=1").status_code == 422
    assert patient.get("/api/search/medicine?q=para&sort=hack").status_code == 422
    assert patient.get("/api/search/medicine?q=%27%20OR%201%3D1%20--").status_code == 200  # SQL treated as text


def test_prescription_pharmacy_ranking_puts_full_coverage_first(login, sql):
    rx = new_prescription(login(DOCTOR))           # needs 60 x med 1 and 30 x med 9
    ensure_stock(sql, 1, 1, 100); ensure_stock(sql, 1, 9, 100)   # pharmacy 1: can fill all
    ensure_stock(sql, 2, 1, 100); ensure_stock(sql, 2, 9, 5)     # pharmacy 2: partial
    ensure_stock(sql, 3, 1, 0); ensure_stock(sql, 3, 9, 0)       # pharmacy 3: nothing
    data = login(PATIENT).get(f"/api/patient/prescriptions/{rx['prescription_id']}/pharmacies?{ELDORET_CBD}").get_json()
    full = [r for r in data["results"] if r["can_fill_all"]]
    assert data["results"][0]["can_fill_all"]
    assert 1 in [r["pharmacy_id"] for r in full] and 2 not in [r["pharmacy_id"] for r in full]
    first_partial = next(i for i, r in enumerate(data["results"]) if not r["can_fill_all"])
    assert all(r["can_fill_all"] for r in data["results"][:first_partial])


def test_pharmacy_list_has_coordinates_for_map(login):
    rows = login(PATIENT).get("/api/pharmacies").get_json()
    assert len(rows) == 4
    assert all(-1 < r["latitude"] < 1 and 35 < r["longitude"] < 36 for r in rows)  # Eldoret area
