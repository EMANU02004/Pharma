# PharmaFinder

Digital prescriptions and pharmacy stock lookup for Uasin Gishu County, Kenya.
ALU BSc Software Engineering Foundations Project, Group 3.

Doctors issue structured prescriptions with a unique code. Patients see their prescriptions, find nearby
pharmacies that have every medicine in stock (with price, distance and opening hours on a map), and share a
prescription with one pharmacy for a limited time. The pharmacist checks the code, dispenses, and stock falls
automatically. A prescription can be filled only once, and every sensitive action is recorded in an audit log.

> **Demo data only.** Every person, pharmacy, licence number and stock level in the seed data is fictional.

## Features

| Feature | Where |
|---|---|
| Registration and login with four roles (patients sign up; admin creates doctors and pharmacists) | `routes/auth.py`, `routes/admin.py`, `security.py` |
| Prescription form, unique code, expiry, alert to the patient when issued | `routes/doctor.py`, `rx.py`, `notify.py` |
| Patient Health Passport (prescription history, status, items) | `routes/patient.py`, `public/patient.html` |
| Share a prescription with one pharmacy for 1–72 hours, revoke any time | `routes/patient.py` |
| Medicine search with filters and sorting, prescription-based pharmacy ranking, Leaflet map | `routes/search.py`, `geo.py`, `public/js/patient.js` |
| Stock management with low/out-of-stock flags and last-update time | `routes/pharmacy.py` |
| Code verification and all-or-nothing dispensing with automatic stock deduction | `routes/pharmacy.py` |
| Admin dashboard, user management, audit log | `routes/admin.py`, `public/admin.html` |

Changes from the original proposal (no QR, reservations, payment, digital signature or doctor verification)
are listed in [docs/DEVIATIONS.md](docs/DEVIATIONS.md).

## Tech stack

Python 3.12+ · Flask 3 · MySQL 8 (PyMySQL) · HTML, CSS, JavaScript · Bootstrap 5 · Leaflet.js + OpenStreetMap ·
pytest · Postman/Newman · Vercel

## Project structure

```
app.py                  Entry point (Vercel imports `app` from here)
pharmafinder/           Flask application
  __init__.py           App factory, JSON format, security headers, static files
  config.py             Settings from environment variables
  db.py                 MySQL connection per request, transactions
  security.py           Password hashing, sessions, role checks, attempt limits
  validation.py         Server-side input validation
  rx.py                 Prescription codes, expiry, access grants
  geo.py                Distance (haversine), opening hours, ranking
  audit.py, notify.py   Audit log and alerts
  routes/               auth, doctor, patient, search, pharmacy, admin
public/                 Frontend (HTML pages, css/, js/, vendor/)
database/schema.sql     MySQL schema (12 tables)
database/seed.py        Creates the schema and loads demo data
tests/                  pytest suite (66 tests)
postman/                Postman collection
docs/                   API reference, architecture diagrams, ERD, test report, deviations
tools/                  Test-report generator
```

## Run it locally

You need Python 3.12 or newer and MySQL 8 (or MariaDB 10.6+).

```bash
git clone https://github.com/EMANU02004/Pharma.git
cd Pharma
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env               # Windows: copy .env.example .env
```

Create a MySQL user that can create databases, and put its details in `.env`:

```sql
CREATE USER 'pharma'@'localhost' IDENTIFIED BY 'pharma_dev';
GRANT ALL PRIVILEGES ON pharmafinder.* TO 'pharma'@'localhost';
GRANT ALL PRIVILEGES ON pharmafinder_test.* TO 'pharma'@'localhost';
```

Create the tables and load the demo data, then start the app:

```bash
python -m database.seed     # drops and recreates all tables
python app.py               # http://localhost:5000
```

### Demo accounts (password `Pharma2026` for all)

| Role | Email |
|---|---|
| Patient | aline.chepkoech@demo.pharmafinder.test (also 24 other patients) |
| Doctor | faith.chebet@demo.pharmafinder.test |
| Pharmacist (Eldoret Town Demo Chemist) | grace.jebet@demo.pharmafinder.test |
| Pharmacist (Kapsoya / Langas / Pioneer) | peter.kibet@, lucy.achieng@, daniel.rotich@demo.pharmafinder.test |
| Admin | admin@demo.pharmafinder.test |

The seed includes 4 pharmacies, 25 patients, 6 doctors, 50 medicines and 3 sample prescriptions
(codes `PF7K-AAA2`, `PF7K-BBB3`, `PF7K-CCC4`).

### Demo script

1. Log in as the doctor, search "Aline", add two medicines and issue the prescription. Note the code.
2. Log in as Aline. The prescription and the alert appear. Click **Find pharmacies with this**: pharmacies
   that can fill everything are listed first, with distance, price and the map.
3. Click **Share here** on the top pharmacy.
4. Log in as that pharmacy's pharmacist, enter the code, then **Dispense all and mark filled**.
5. Enter the code again: it is refused as already filled. Check **Stock**: quantities have dropped.
6. Log in as admin and open **Audit log** to see every step.

## Tests

```bash
python -m pytest                    # 66 tests; uses a separate pharmafinder_test database
python tools/make_test_report.py    # runs the tests and writes docs/TEST_REPORT.md
npx newman run postman/PharmaFinder.postman_collection.json   # with the app running and freshly seeded
```

The tests rebuild the test database from `schema.sql` before every test and run against real MySQL, not mocks.
Latest results: [docs/TEST_REPORT.md](docs/TEST_REPORT.md) (66/66 pytest) and
[docs/POSTMAN_RUN.txt](docs/POSTMAN_RUN.txt) (30/30 Postman assertions).

## Deploy to Vercel

Vercel runs the Flask app as a serverless function and serves `public/` from its CDN. It does not host MySQL,
so the database lives elsewhere, for example a free [Aiven for MySQL](https://aiven.io/mysql) service.

1. **Database:** create a MySQL service on Aiven. Download its CA certificate. From your own computer, point
   `.env` at it (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME=defaultdb`,
   `DB_SSL_CA=path/to/ca.pem`) and run `python -m database.seed` once.
2. **Certificate:** copy the CA file into the repo as `certs/aiven-ca.pem`. It is a public certificate, not a
   secret, but `.gitignore` ignores `certs/*.pem`, so add it with `git add -f certs/aiven-ca.pem`.
3. **Vercel project:** import the GitHub repo at <https://vercel.com/new>. Vercel detects Flask from
   `requirements.txt` and `app.py`.
4. **Environment variables** (Project → Settings → Environment Variables): `SECRET_KEY` (a long random string),
   `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_SSL_CA=certs/aiven-ca.pem`,
   `SESSION_COOKIE_SECURE=true`. Optionally `SMTP_*` for real email alerts.
5. **Deploy**, then open `/api/health`. It should return `{"status":"ok"}`.

Design choices that make this work on serverless hosting: prescription expiry is applied whenever
prescriptions are read (no background job needed), attempt limits are counted from the audit log (no
in-memory state), and nothing is written to disk.

## Security measures actually implemented

- Passwords hashed with scrypt and a random salt (Werkzeug); never stored or logged in plain text.
- Signed, HttpOnly, SameSite=Lax session cookies (`Secure` when `SESSION_COOKIE_SECURE=true`).
- Role checks and ownership checks on the server for every endpoint; records you cannot access return 404.
- Self-registration can only create patient accounts.
- All SQL uses parameters (no string-built queries with user input).
- Database `CHECK`, `UNIQUE` and foreign-key constraints back up the API's validation.
- Dispensing runs in one transaction with row locks, so a prescription is filled once and stock cannot go negative.
- Limits on failed logins (5) and failed code checks (10) per 15 minutes.
- Audit log of logins, prescription, access, stock, dispensing and admin actions.
- Frontend escapes all server data before inserting it into the page; security headers on every response.

Not implemented (do not claim): encryption of data at rest, anonymised search, account deletion/export.

## Team

| Member | Role |
|---|---|
| Pauline Miyienda | Frontend developer, project manager |
| Marion Gitau | Backend developer |
| Emmanuel Masambu | Database architect |
| Sylvie Uwera | Frontend developer |
| Ahmed Osman | UI/UX designer |
| Batsinda Benoit | Backend developer |
