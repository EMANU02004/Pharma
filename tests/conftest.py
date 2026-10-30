"""Test fixtures. Tests run against a real MySQL/MariaDB database
(`<DB_NAME>_test`), rebuilt from schema.sql + seed data before every test."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from database import seed as seed_module  # noqa: E402
from pharmafinder import create_app  # noqa: E402
from pharmafinder.config import Config  # noqa: E402

TEST_DB = os.environ.get("TEST_DB_NAME", Config.DB_NAME + "_test")
PASSWORD = "Pharma2026"

ADMIN = "admin@demo.pharmafinder.test"
DOCTOR = "faith.chebet@demo.pharmafinder.test"
DOCTOR2 = "kevin.kiprono@demo.pharmafinder.test"
PHARMACIST = "grace.jebet@demo.pharmafinder.test"      # pharmacy 1
PHARMACIST2 = "peter.kibet@demo.pharmafinder.test"     # pharmacy 2
PATIENT = "aline.chepkoech@demo.pharmafinder.test"     # patient 1
PATIENT2 = "john.kiptoo@demo.pharmafinder.test"        # patient 2


def _rebuild():
    Config.DB_NAME = TEST_DB
    conn = seed_module.connect(with_db=False)
    with conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{TEST_DB}` CHARACTER SET utf8mb4")
    conn.close()
    conn = seed_module.connect()
    with conn.cursor() as cur:
        seed_module.run_schema(cur)
        seed_module.seed(cur, password=PASSWORD)
    conn.close()


@pytest.fixture()
def app():
    _rebuild()
    application = create_app({"TESTING": True, "DB_NAME": TEST_DB, "SMTP_HOST": None})
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def login(app):
    """login(email) -> a test client already logged in as that user."""
    def _login(email, password=PASSWORD):
        c = app.test_client()
        r = c.post("/api/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.get_json()
        return c
    return _login


@pytest.fixture()
def sql(app):
    """Run a query directly against the test database (for asserting DB state)."""
    def _sql(statement, params=None):
        conn = seed_module.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(statement, params or ())
                return cur.fetchall()
        finally:
            conn.close()
    return _sql


def new_prescription(doctor_client, patient_id=1, items=None, valid_days=30):
    items = items or [
        {"medicine_id": 1, "dose": "1 tablet", "frequency": "Twice daily", "duration_days": 30, "quantity": 60},
        {"medicine_id": 9, "dose": "1 tablet", "frequency": "Once daily", "duration_days": 30, "quantity": 30},
    ]
    r = doctor_client.post("/api/doctor/prescriptions",
                           json={"patient_id": patient_id, "items": items, "valid_days": valid_days})
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def share(patient_client, rx_id, pharmacy_id=1, hours=24):
    r = patient_client.post(f"/api/patient/prescriptions/{rx_id}/grants",
                            json={"pharmacy_id": pharmacy_id, "hours": hours})
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def ensure_stock(sql, pharmacy_id, medicine_id, quantity, price=10):
    sql("INSERT INTO item_stock (pharmacy_id, medicine_id, price_kes, quantity) VALUES (%s,%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE quantity=VALUES(quantity)", (pharmacy_id, medicine_id, price, quantity))
