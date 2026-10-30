"""GrantAccess: patients share a prescription with one pharmacy and can revoke it."""
from conftest import DOCTOR, PATIENT, PATIENT2, PHARMACIST, PHARMACIST2, new_prescription, share


def test_unshared_prescription_cannot_be_opened_by_pharmacy(login):
    rx = new_prescription(login(DOCTOR))
    r = login(PHARMACIST).post("/api/pharmacy/verify", json={"code": rx["code"]})
    assert r.status_code == 404
    assert "shared" in r.get_json()["error"]


def test_shared_prescription_opens_only_at_that_pharmacy(login):
    rx = new_prescription(login(DOCTOR))
    share(login(PATIENT), rx["prescription_id"], pharmacy_id=1)
    assert login(PHARMACIST).post("/api/pharmacy/verify", json={"code": rx["code"]}).status_code == 200
    assert login(PHARMACIST2).post("/api/pharmacy/verify", json={"code": rx["code"]}).status_code == 404
    shared = login(PHARMACIST).get("/api/pharmacy/shared").get_json()
    assert rx["code"] in [s["code"] for s in shared]


def test_revoked_access_blocks_pharmacy_immediately(login, sql):
    rx = new_prescription(login(DOCTOR))
    patient = login(PATIENT)
    grant = share(patient, rx["prescription_id"])
    pharmacist = login(PHARMACIST)
    assert pharmacist.post("/api/pharmacy/verify", json={"code": rx["code"]}).status_code == 200
    assert patient.post(f"/api/patient/grants/{grant['grant_id']}/revoke").status_code == 200
    assert pharmacist.post("/api/pharmacy/verify", json={"code": rx["code"]}).status_code == 404
    assert pharmacist.post("/api/pharmacy/dispense", json={"code": rx["code"]}).status_code == 404
    assert sql("SELECT COUNT(*) n FROM audit_log WHERE action='REVOKE_ACCESS'")[0]["n"] == 1


def test_expired_access_blocks_pharmacy(login, sql):
    rx = new_prescription(login(DOCTOR))
    grant = share(login(PATIENT), rx["prescription_id"])
    sql("UPDATE grant_access SET granted_at = NOW() - INTERVAL 2 DAY, expires_at = NOW() - INTERVAL 1 DAY "
        "WHERE grant_id=%s", (grant["grant_id"],))
    assert login(PHARMACIST).post("/api/pharmacy/verify", json={"code": rx["code"]}).status_code == 404


def test_patient_cannot_share_or_revoke_someone_elses_prescription(login):
    rx = new_prescription(login(DOCTOR), patient_id=1)
    grant = share(login(PATIENT), rx["prescription_id"])
    other = login(PATIENT2)
    assert other.post(f"/api/patient/prescriptions/{rx['prescription_id']}/grants",
                      json={"pharmacy_id": 2}).status_code == 404
    assert other.post(f"/api/patient/grants/{grant['grant_id']}/revoke").status_code == 404


def test_grant_duration_is_limited(login):
    rx = new_prescription(login(DOCTOR))
    patient = login(PATIENT)
    r = patient.post(f"/api/patient/prescriptions/{rx['prescription_id']}/grants",
                     json={"pharmacy_id": 1, "hours": 500})
    assert r.status_code == 422
    r = patient.post(f"/api/patient/prescriptions/{rx['prescription_id']}/grants",
                     json={"pharmacy_id": 999})
    assert r.status_code == 404
