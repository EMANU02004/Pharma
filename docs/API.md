# PharmaFinder REST API

Base URL: `http://localhost:5000` locally, or your Vercel URL.
All requests and responses are JSON. Requests with a body must send `Content-Type: application/json`.

**Authentication:** log in with `POST /api/auth/login`. The server sets a signed, HttpOnly session cookie,
which the browser (or Postman) sends with every later request.

**Errors** always look like this, with an HTTP status code:

```json
{ "error": "Missing required fields", "fields": { "dose": "This field is required" } }
```

| Status | Meaning |
|---|---|
| 401 | Not logged in, or the account was deactivated |
| 403 | Logged in, but this role may not do this |
| 404 | Not found, or not yours (the API does not reveal records you cannot access) |
| 409 | Conflict with the current state (already filled, expired, duplicate) |
| 415 | Body was not JSON |
| 422 | Invalid input; `fields` names the problem fields |
| 429 | Too many failed attempts (login or code checks), try again in 15 minutes |

## Auth (`/api/auth`)

| Method | Path | Who | Body / notes |
|---|---|---|---|
| POST | `/register` | Anyone | `full_name, email, password` (8+ chars, letters and numbers), optional `phone, date_of_birth (YYYY-MM-DD), sub_county`. Always creates a **patient**; any `role` sent is ignored. Logs the new user in. |
| POST | `/login` | Anyone | `email, password` → `{user_id, role, full_name}`. 5 failures in 15 min → 429. |
| POST | `/logout` | Anyone | Ends the session. |
| GET | `/me` | Logged in | Current user, with `patient_id`, `doctor_id` or `pharmacy_id` and `pharmacy_name`. |

## Shared (`/api`, any logged-in user)

| Method | Path | Notes |
|---|---|---|
| GET | `/medicines?q=` | Catalogue search by brand or generic name. |
| GET | `/pharmacies` | Active pharmacies with coordinates, hours and `open_now`. |
| GET | `/search/medicine?q=&lat=&lng=&sort=&in_stock=&open_now=&max_km=&min_qty=` | Pharmacies stocking the medicine. `q` 2+ chars. `sort` = `distance` (default), `price` or `stock`. `in_stock` defaults to 1. Each result has `price_kes, quantity, stock_level (ok/low/out), distance_km, open_now, updated_at`. |
| GET | `/notifications` | Your latest 50 alerts, with `delivery_status` (`simulated` when no email is configured). |
| POST | `/notifications/{id}/read` | Mark an alert read. |
| GET | `/health` | `{"status":"ok"}` when the API can reach MySQL. |

## Doctor (`/api/doctor`)

| Method | Path | Notes |
|---|---|---|
| GET | `/patients?q=` | Search patients by name or email (max 25). |
| POST | `/prescriptions` | Body below. Validates every field, generates the code, sets the expiry, writes the audit row and alerts the patient. 201 returns the full prescription plus `notification`. |
| GET | `/prescriptions` | Prescriptions you issued. |
| POST | `/prescriptions/{id}/cancel` | Only your own, only while active. |

```json
{
  "patient_id": 1,
  "valid_days": 30,
  "notes": "Review in one month",
  "items": [
    { "medicine_id": 1, "dose": "1 tablet", "frequency": "Twice daily", "duration_days": 30, "quantity": 60 }
  ]
}
```

Rules: 1–20 items, each medicine once; `duration_days` 1–365; `quantity` 1–1000; `valid_days` 1–90 (default 30).

## Patient (`/api/patient`)

| Method | Path | Notes |
|---|---|---|
| GET | `/prescriptions` | Your Health Passport: prescriptions with items, status and `grants`. Overdue prescriptions are marked `expired` when read. |
| GET | `/prescriptions/{id}` | One of yours (404 if not yours). |
| GET | `/prescriptions/{id}/pharmacies?lat=&lng=` | Every active pharmacy with what it can supply for this prescription: `items_available, can_fill_all, total_price_kes, distance_km, lines[]`. Ranked: can fill everything first, then more items, then distance, then price. |
| POST | `/prescriptions/{id}/grants` | `{pharmacy_id, hours}` (1–72, default 24). Lets that pharmacy open the prescription until `expires_at`. Only active prescriptions. Replaces an existing live grant for the same pharmacy. |
| GET | `/grants` | All your grants with `state` = `active`, `expired` or `revoked`. |
| POST | `/grants/{id}/revoke` | Ends access immediately. |

## Pharmacist (`/api/pharmacy`) – always limited to the pharmacist's own pharmacy

| Method | Path | Notes |
|---|---|---|
| GET | `/stock` | Your stock with `stock_level`, a `summary` (total/low/out) and `last_updated`. Low stock = fewer than 10. |
| POST | `/stock` | `{medicine_id, quantity (>= 0), price_kes (> 0)}`. 409 if already stocked. |
| PATCH | `/stock/{stock_id}` | `{quantity?, price_kes?}`. 404 for another pharmacy's line. |
| POST | `/medicines` | `{brand_name, generic_name, strength_form, requires_prescription}` adds to the shared catalogue. |
| POST | `/verify` | `{code}` (case and spaces ignored). Works only if the patient has shared it with your pharmacy. Returns the prescription, your stock per item, `can_dispense`, `blocked_reason` and `total_price_kes`. Wrong or unshared codes → 404; 10 failures in 15 min → 429. |
| POST | `/dispense` | `{code}`. In one transaction with row locks: checks the grant, status and expiry, checks stock for every item, subtracts it, marks the prescription `filled`, closes grants, audits and alerts the patient. Second attempt → 409. Short of any item → 409 and nothing changes. |
| GET | `/shared` | Prescriptions currently shared with your pharmacy. |
| GET | `/dispensed` | Your last 50 dispensed prescriptions. |

## Admin (`/api/admin`)

| Method | Path | Notes |
|---|---|---|
| GET | `/stats` | Counts of users by role, prescriptions by status, pharmacies, medicines and audit events in 24 h. |
| GET | `/users?role=&q=` | Users with doctor licence/facility or pharmacy name. |
| POST | `/doctors` | `{full_name, email, password, phone?, license_number, speciality?, facility?}` |
| POST | `/pharmacists` | `{full_name, email, password, phone?, license_number, pharmacy_id}` |
| GET / POST | `/pharmacies` | List, or create `{name, license_number, address, latitude, longitude, open_days?, opens_at?, closes_at?}` (times `HH:MM`). |
| POST | `/users/{id}/status` | `{is_active: true|false}`. Takes effect on the user's next request. You cannot deactivate yourself. |
| GET | `/audit?action=&limit=` | Latest audit entries (max 500) and the list of action names. |

### Audit actions recorded

`REGISTER, LOGIN, LOGIN_FAILED, CREATE_PRESCRIPTION, CANCEL_PRESCRIPTION, GRANT_ACCESS, REVOKE_ACCESS,
VERIFY_PRESCRIPTION, VERIFY_FAILED, DISPENSE, STOCK_ADD, STOCK_UPDATE, MEDICINE_ADD, CREATE_DOCTOR,
CREATE_PHARMACIST, CREATE_PHARMACY, ACTIVATE_USER, DEACTIVATE_USER`
