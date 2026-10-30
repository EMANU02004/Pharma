"""Authentication, registration and role-based access control."""
from conftest import ADMIN, DOCTOR, PATIENT, PHARMACIST


def _register(client, **overrides):
    body = {"full_name": "Test Patient", "email": "new.patient@example.com", "password": "Strong123",
            "phone": "0712345678", "date_of_birth": "1990-05-01", "sub_county": "Kesses"}
    body.update(overrides)
    return client.post("/api/auth/register", json=body)


def test_register_creates_patient_and_logs_in(client, sql):
    r = _register(client)
    assert r.status_code == 201
    assert r.get_json()["role"] == "patient"
    assert client.get("/api/auth/me").get_json()["role"] == "patient"
    row = sql("SELECT password_hash FROM users WHERE email='new.patient@example.com'")[0]
    assert "Strong123" not in row["password_hash"]


def test_register_cannot_choose_doctor_or_admin_role(client, sql):
    for role in ("doctor", "pharmacist", "admin"):
        r = _register(client, email=f"sneaky.{role}@example.com", role=role)
        assert r.status_code == 201
        assert r.get_json()["role"] == "patient"
    assert sql("SELECT COUNT(*) n FROM users WHERE email LIKE 'sneaky.%%' AND role <> 'patient'")[0]["n"] == 0


def test_register_rejects_duplicate_email_and_bad_input(client):
    assert _register(client, email=PATIENT).status_code == 409
    assert _register(client, email="not-an-email").status_code == 422
    assert _register(client, password="weak").status_code == 422
    assert _register(client, full_name="").status_code == 422
    assert client.post("/api/auth/register", data="x").status_code == 415


def test_login_success_and_failure(client):
    assert client.post("/api/auth/login", json={"email": DOCTOR, "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "nobody@x.com", "password": "Pharma2026"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": DOCTOR, "password": "Pharma2026"})
    assert r.status_code == 200 and r.get_json()["role"] == "doctor"


def test_login_is_rate_limited_after_repeated_failures(client):
    for _ in range(5):
        client.post("/api/auth/login", json={"email": DOCTOR, "password": "wrong"})
    r = client.post("/api/auth/login", json={"email": DOCTOR, "password": "Pharma2026"})
    assert r.status_code == 429


def test_logout_ends_session(login):
    c = login(PATIENT)
    assert c.get("/api/auth/me").status_code == 200
    c.post("/api/auth/logout")
    assert c.get("/api/auth/me").status_code == 401


def test_protected_endpoints_require_login(client):
    for url in ("/api/patient/prescriptions", "/api/doctor/prescriptions", "/api/pharmacy/stock",
                "/api/admin/users", "/api/medicines", "/api/search/medicine?q=para"):
        assert client.get(url).status_code == 401, url


def test_cross_role_access_is_forbidden(login):
    patient, doctor, pharmacist = login(PATIENT), login(DOCTOR), login(PHARMACIST)
    assert patient.get("/api/doctor/prescriptions").status_code == 403
    assert patient.post("/api/doctor/prescriptions", json={"patient_id": 1, "items": []}).status_code == 403
    assert patient.get("/api/pharmacy/stock").status_code == 403
    assert patient.get("/api/admin/users").status_code == 403
    assert doctor.post("/api/pharmacy/dispense", json={"code": "PF7K-AAA2"}).status_code == 403
    assert doctor.get("/api/patient/prescriptions").status_code == 403
    assert pharmacist.post("/api/doctor/prescriptions", json={}).status_code == 403
    assert pharmacist.get("/api/admin/audit").status_code == 403


def test_deactivated_user_loses_access_immediately(login, sql):
    patient = login(PATIENT)
    admin = login(ADMIN)
    uid = sql("SELECT user_id FROM users WHERE email=%s", (PATIENT,))[0]["user_id"]
    assert admin.post(f"/api/admin/users/{uid}/status", json={"is_active": False}).status_code == 200
    assert patient.get("/api/patient/prescriptions").status_code == 401
    c = patient.post("/api/auth/login", json={"email": PATIENT, "password": "Pharma2026"})
    assert c.status_code == 403
