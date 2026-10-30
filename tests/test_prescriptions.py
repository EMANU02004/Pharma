"""Prescription creation, validation, notification, history and patient privacy."""
from conftest import DOCTOR, DOCTOR2, PATIENT, PATIENT2, new_prescription

GOOD_ITEM = {"medicine_id": 1, "dose": "1 tablet", "frequency": "Twice daily", "duration_days": 30, "quantity": 60}


def test_doctor_creates_prescription_with_code_and_expiry(login, sql):
    rx = new_prescription(login(DOCTOR))
    assert rx["status"] == "active"
    assert len(rx["code"]) == 9 and rx["code"][4] == "-"
    assert len(rx["items"]) == 2
    assert rx["expiry_date"] > rx["issue_date"]
    assert sql("SELECT COUNT(*) n FROM audit_log WHERE action='CREATE_PRESCRIPTION' AND target_id=%s",
               (rx["prescription_id"],))[0]["n"] == 1


def test_prescription_issue_alert_reaches_patient(login):
    rx = new_prescription(login(DOCTOR))
    assert rx["notification"] == "simulated"   # no SMTP configured in tests
    notes = login(PATIENT).get("/api/notifications").get_json()
    assert notes[0]["subject"] == "New prescription issued"
    assert rx["code"] in notes[0]["body"]
    assert notes[0]["delivery_status"] == "simulated"


def test_prescription_with_missing_fields_is_rejected(login, sql):
    doctor = login(DOCTOR)
    before = sql("SELECT COUNT(*) n FROM prescriptions")[0]["n"]
    cases = [
        {"items": [GOOD_ITEM]},                                           # no patient
        {"patient_id": 1, "items": []},                                   # no medicines
        {"patient_id": 1, "items": [{**GOOD_ITEM, "dose": ""}]},          # missing dose
        {"patient_id": 1, "items": [{**GOOD_ITEM, "frequency": None}]},   # missing frequency
        {"patient_id": 1, "items": [{**GOOD_ITEM, "duration_days": 0}]},  # invalid duration
        {"patient_id": 1, "items": [{**GOOD_ITEM, "quantity": -3}]},      # invalid quantity
        {"patient_id": 1, "items": [{**GOOD_ITEM, "medicine_id": 99999}]},  # unknown medicine
        {"patient_id": 1, "items": [GOOD_ITEM, GOOD_ITEM]},               # duplicate medicine
        {"patient_id": 1, "items": [GOOD_ITEM], "valid_days": 400},       # too long validity
        {"patient_id": 9999, "items": [GOOD_ITEM]},                       # unknown patient
    ]
    for body in cases:
        r = doctor.post("/api/doctor/prescriptions", json=body)
        assert r.status_code in (404, 422), (body, r.get_json())
    assert sql("SELECT COUNT(*) n FROM prescriptions")[0]["n"] == before


def test_patient_sees_only_own_prescriptions(login):
    rx = new_prescription(login(DOCTOR), patient_id=1)
    mine = login(PATIENT).get("/api/patient/prescriptions").get_json()
    assert rx["prescription_id"] in [p["prescription_id"] for p in mine]
    other = login(PATIENT2)
    assert rx["prescription_id"] not in [p["prescription_id"] for p in other.get("/api/patient/prescriptions").get_json()]
    assert other.get(f"/api/patient/prescriptions/{rx['prescription_id']}").status_code == 404


def test_doctor_cancels_only_own_active_prescription(login):
    rx = new_prescription(login(DOCTOR))
    rid = rx["prescription_id"]
    assert login(DOCTOR2).post(f"/api/doctor/prescriptions/{rid}/cancel").status_code == 404
    doctor = login(DOCTOR)
    assert doctor.post(f"/api/doctor/prescriptions/{rid}/cancel").status_code == 200
    assert doctor.post(f"/api/doctor/prescriptions/{rid}/cancel").status_code == 409


def test_overdue_prescription_becomes_expired(login, sql):
    rx = new_prescription(login(DOCTOR))
    sql("UPDATE prescriptions SET issue_date = CURDATE() - INTERVAL 40 DAY, "
        "expiry_date = CURDATE() - INTERVAL 1 DAY WHERE prescription_id=%s", (rx["prescription_id"],))
    got = login(PATIENT).get(f"/api/patient/prescriptions/{rx['prescription_id']}").get_json()
    assert got["status"] == "expired"


def test_doctor_patient_search(login):
    r = login(DOCTOR).get("/api/doctor/patients?q=aline")
    assert r.status_code == 200
    assert r.get_json()[0]["full_name"] == "Aline Chepkoech"
