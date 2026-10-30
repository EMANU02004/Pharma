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

## How to commit (in this order)

The code is complete on `feature/full-implementation` (pull request #1). To give each member their own commits, we rebuild it on a new branch, one person at a time, **in the order of the table above** (database first, design last). Each person waits for the previous person to push.

1. Download your package `PharmaFinder_<YourName>.zip` from the team chat.
2. Run these commands in your clone of the repo:

```bash
git fetch origin
git checkout team-build 2>/dev/null || git checkout -b team-build origin/main   # Emmanuel creates it, others check it out
git pull origin team-build                                                  # skip if you are first
```

3. Unzip your package **into the root of the repo** so the folders line up (for example `pharmafinder/...` lands in `pharmafinder/`).
4. Read every file you are adding. Run the app and the tests once the pieces you depend on are in.
5. Commit and push:

```bash
git add -A
git commit -m "Add <your area>: <short description>"
git push -u origin team-build
```

6. Tell the next person in the table it is their turn.

After Ahmed's commit the branch is identical to pull request #1. Pauline then opens a pull request from `team-build` to `main`, everyone reviews, and pull request #1 is closed without merging.

## Honesty note

The code was written with AI assistance, which is permitted for this project and acknowledged on slide 14. Committing a file means you take ownership of it: read it, run it, and be ready to explain it. Do not claim in the teamwork report that you wrote it unaided.
