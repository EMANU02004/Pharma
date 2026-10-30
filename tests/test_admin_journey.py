"""Admin features and the full end-to-end system journey."""
from conftest import DOCTOR, PATIENT, PHARMACIST, ensure_stock


def test_admin_creates_pharmacy_and_staff_who_can_log_in(login, client):
    admin = login("admin@demo.pharmafinder.test")
    ph = admin.post("/api/admin/pharmacies", json={
        "name": "Moiben Test Pharmacy", "license_number": "TEST-PH-9", "address": "Moiben",
        "latitude": 0.8100, "longitude": 35.3800, "open_days": "Mon-Sat", "opens_at": "08:00", "closes_at": "19:00"})
    assert ph.status_code == 201
    r = admin.post("/api/admin/pharmacists", json={
        "full_name": "New Pharmacist", "email": "new.pharm@example.com", "password": "Pharma2026",
        "license_number": "TEST-PS-9", "pharmacy_id": ph.get_json()["pharmacy_id"]})
    assert r.status_code == 201
    r = admin.post("/api/admin/doctors", json={
        "full_name": "Dr. New", "email": "dr.new@example.com", "password": "Pharma2026",
        "license_number": "TEST-MD-9", "facility": "Test Clinic"})
    assert r.status_code == 201
    assert client.post("/api/auth/login", json={"email": "dr.new@example.com", "password": "Pharma2026"}).get_json()["role"] == "doctor"


def test_admin_input_validation_and_duplicates(login):
    admin = login("admin@demo.pharmafinder.test")
    assert admin.post("/api/admin/doctors", json={"full_name": "X", "email": "x@example.com", "password": "Pharma2026",
                                                  "license_number": "DEMO-MD-1001"}).status_code == 409
    assert admin.post("/api/admin/pharmacies", json={"name": "Bad", "license_number": "B-1", "address": "x",
                                                     "latitude": 200, "longitude": 35}).status_code == 422
    assert admin.post("/api/admin/pharmacies", json={"name": "Bad", "license_number": "B-2", "address": "x",
                                                     "latitude": 0.5, "longitude": 35, "opens_at": "25:99"}).status_code == 422


def test_audit_log_lists_actions(login):
    admin = login("admin@demo.pharmafinder.test")
    data = admin.get("/api/admin/audit").get_json()
    assert "LOGIN" in data["actions"]
    assert data["entries"][0]["created_at"] is not None


def test_full_journey(login, sql):
    """Doctor issues -> patient sees and searches -> patient shares -> pharmacist
    verifies and dispenses -> stock falls -> prescription is filled -> audit trail exists."""
    ensure_stock(sql, 1, 1, 200)
    ensure_stock(sql, 1, 9, 200)
    doctor, patient, pharmacist = login(DOCTOR), login(PATIENT), login(PHARMACIST)

    # 1. Doctor creates the prescription
    rx = doctor.post("/api/doctor/prescriptions", json={"patient_id": 1, "items": [
        {"medicine_id": 1, "dose": "1 tablet", "frequency": "Twice daily", "duration_days": 30, "quantity": 60},
        {"medicine_id": 9, "dose": "1 tablet", "frequency": "Once daily", "duration_days": 30, "quantity": 30}]}).get_json()

    # 2. Patient gets the alert and sees it in the Health Passport
    assert patient.get("/api/notifications").get_json()[0]["subject"] == "New prescription issued"
    mine = patient.get("/api/patient/prescriptions").get_json()
    assert rx["code"] in [p["code"] for p in mine]

    # 3. Patient finds nearby pharmacies that can fill it
    ranked = patient.get(f"/api/patient/prescriptions/{rx['prescription_id']}/pharmacies?lat=0.5143&lng=35.2698").get_json()
    assert ranked["results"][0]["can_fill_all"]

    # 4. Patient shares it with pharmacy 1
    assert patient.post(f"/api/patient/prescriptions/{rx['prescription_id']}/grants",
                        json={"pharmacy_id": 1, "hours": 24}).status_code == 201

    # 5. Pharmacist verifies the code and dispenses
    assert pharmacist.post("/api/pharmacy/verify", json={"code": rx["code"]}).get_json()["can_dispense"]
    assert pharmacist.post("/api/pharmacy/dispense", json={"code": rx["code"]}).status_code == 200

    # 6. Stock decreased and prescription is filled
    stock = {r["medicine_id"]: r["quantity"] for r in sql(
        "SELECT medicine_id, quantity FROM item_stock WHERE pharmacy_id=1 AND medicine_id IN (1, 9)")}
    assert stock == {1: 140, 9: 170}
    assert patient.get(f"/api/patient/prescriptions/{rx['prescription_id']}").get_json()["status"] == "filled"

    # 7. Every step is in the audit log
    actions = {r["action"] for r in sql("SELECT action FROM audit_log WHERE target_id=%s AND target_type='prescription'",
                                        (rx["prescription_id"],))}
    assert {"CREATE_PRESCRIPTION", "GRANT_ACCESS", "VERIFY_PRESCRIPTION", "DISPENSE"} <= actions
