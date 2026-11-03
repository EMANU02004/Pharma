# Code ownership

Each file in the repo has one owner. The owner commits it from their own GitHub account, reviews it, and must be able to explain it in Q&A (the slides they present match the code they own).

| # | Owner | Role | Presents slides | Responsible for |
|---|---|---|---|---|
| 1 | Emmanuel Masambu | Database architect | 6, 10 | The 12-table schema, keys and CHECK constraints; the seed data; the database connection and transactions; the test set-up and test report. |
| 2 | Marion Gitau | Backend developer | 4, 5 | App start-up, configuration, error format, password hashing, sessions and role checks, input validation, audit log writer; login/registration, admin and doctor endpoints. |
| 3 | Batsinda Benoit | Backend developer | 7, 9 | Prescription codes and expiry, alerts, sharing and revoking, verification and the single-use dispensing transaction; Postman collection. |
| 4 | Sylvie Uwera | Frontend developer | 8, 12 | Haversine distance, opening hours and the ranking algorithm; medicine search API; the patient page with the Leaflet map. |
| 5 | Pauline Miyienda | Frontend developer, project manager | 1, 2, 3, 14 | Login page, shared frontend helpers (api.js), doctor and pharmacist pages; README and the list of changes from the proposal. |
| 6 | Ahmed Osman | UI/UX designer | 11, 13 | Visual design (app.css), Bootstrap/Leaflet/fonts bundle, admin page, screenshots and the presentation. |

## Files by owner

### Emmanuel Masambu

- `database/__init__.py`
- `database/schema.sql`
- `database/seed.py`
- `docs/ARCHITECTURE.md`
- `docs/TEST_REPORT.md`
- `pharmafinder/db.py`
- `pytest.ini`
- `tests/conftest.py`
- `tests/test_prescriptions.py`
- `tests/test_unit.py`
- `tools/make_test_report.py`
- `docs/diagrams/` (all files)

### Marion Gitau

- `.env.example`
- `.gitignore`
- `app.py`
- `docs/API.md`
- `pharmafinder/__init__.py`
- `pharmafinder/audit.py`
- `pharmafinder/config.py`
- `pharmafinder/errors.py`
- `pharmafinder/routes/__init__.py`
- `pharmafinder/routes/admin.py`
- `pharmafinder/routes/auth.py`
- `pharmafinder/routes/doctor.py`
- `pharmafinder/security.py`
- `pharmafinder/validation.py`
- `requirements-dev.txt`
- `requirements.txt`
- `tests/test_admin_journey.py`
- `tests/test_auth.py`

### Batsinda Benoit

- `docs/POSTMAN_RUN.txt`
- `pharmafinder/notify.py`
- `pharmafinder/routes/patient.py`
- `pharmafinder/routes/pharmacy.py`
- `pharmafinder/rx.py`
- `postman/PharmaFinder.postman_collection.json`
- `tests/test_dispense.py`
- `tests/test_sharing.py`

### Sylvie Uwera

- `pharmafinder/geo.py`
- `pharmafinder/routes/search.py`
- `public/js/patient.js`
- `public/patient.html`
- `tests/test_stock_search.py`

### Pauline Miyienda

- `README.md`
- `docs/DEVIATIONS.md`
- `public/doctor.html`
- `public/index.html`
- `public/js/api.js`
- `public/js/doctor.js`
- `public/js/pharmacist.js`
- `public/pharmacist.html`
- `docs/CODE_OWNERSHIP.md`

### Ahmed Osman

- `docs/presentation/PharmaFinder_Technical_Presentation.pdf`
- `docs/presentation/PharmaFinder_Technical_Presentation.pptx`
- `docs/presentation/SPEAKER_SCRIPT.md`
- `public/admin.html`
- `public/css/app.css`
- `public/js/admin.js`
- `docs/screenshots/` (all files)
- `public/vendor/` (all files)

## How to review and commit your area

The full implementation is already on `main` (pull request #1, merged 30 October). Each member now reviews the files they own, learns how they work, and commits at least one real improvement from their own GitHub account.

1. Update your clone and make a branch named after you:

```bash
git checkout main
git pull origin main
git checkout -b review/<your-name>
```

2. Read every file listed under your name above. Run the app and the tests for your area (see the README).
3. Make at least one real improvement: comments explaining the tricky parts, a fix you found while reading, or an extra test.
4. Commit and push from your own account:

```bash
git add -A
git commit -m "Review <your area>: <what you changed>"
git push -u origin review/<your-name>
```

5. Open a pull request into `main`, ask one teammate to review it, and merge after their approval.

## Honesty note

The code was written with AI assistance, which is permitted for this project. Committing a file means you take ownership of it: read it, run it, and be ready to explain it. Do not claim in the teamwork report that you wrote it unaided.
