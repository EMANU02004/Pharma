# PharmaFinder test report

Generated 2026-10-30 11:32 by `tools/make_test_report.py` from a real pytest run against a MySQL-compatible database rebuilt from `database/schema.sql` and seed data before each test.

**Result: 66 passed, 0 failed** (pytest: `66 passed in 19.42s`)

## Unit tests (22)

| # | Test case | Expected result | Actual result | Status |
|---|---|---|---|---|
| 1 | Distance from a point to itself | 0 km | As expected | Pass |
| 2 | Haversine distance Eldoret to Nairobi | About 263 km (+/- 5) | As expected | Pass |
| 3 | Opening-day parsing (Mon-Sat, Mon-Fri,Sun, Daily, Fri-Mon) | Correct weekday sets | As expected | Pass |
| 4 | Open-now check by day and time | Open Wed 10:00; closed Wed 21:00 and Sunday | As expected | Pass |
| 5 | Prescription ranking algorithm | Full coverage first, then distance | As expected | Pass |
| 6 | 2,000 generated prescription codes | All XXXX-XXXX, unambiguous alphabet, no duplicates | As expected | Pass |
| 7 | Code normalisation | Lower case/spaces accepted; wrong length, O/1 and SQL text rejected | As expected | Pass |
| 8 | Password hashing | Different salted hashes; correct password verifies, wrong one fails | As expected | Pass |
| 9 | Weak password rules `[short1]` | Rejected | As expected | Pass |
| 10 | Weak password rules `[allletters]` | Rejected | As expected | Pass |
| 11 | Weak password rules `[12345678]` | Rejected | As expected | Pass |
| 12 | Weak password rules `[None]` | Rejected | As expected | Pass |
| 13 | Weak password rules `[123]` | Rejected | As expected | Pass |
| 14 | Quantity validation `[-1]` | Negative, text, decimal, boolean rejected | As expected | Pass |
| 15 | Quantity validation `[abc]` | Negative, text, decimal, boolean rejected | As expected | Pass |
| 16 | Quantity validation `[1.5]` | Negative, text, decimal, boolean rejected | As expected | Pass |
| 17 | Quantity validation `[True]` | Negative, text, decimal, boolean rejected | As expected | Pass |
| 18 | Quantity validation `[None]` | Negative, text, decimal, boolean rejected | As expected | Pass |
| 19 | Price validation `[0]` | Zero, negative, text rejected | As expected | Pass |
| 20 | Price validation `[-5]` | Zero, negative, text rejected | As expected | Pass |
| 21 | Price validation `[free]` | Zero, negative, text rejected | As expected | Pass |
| 22 | Price validation `[None]` | Zero, negative, text rejected | As expected | Pass |

## Integration tests (21)

| # | Test case | Expected result | Actual result | Status |
|---|---|---|---|---|
| 1 | Admin creates pharmacy, pharmacist and doctor | All 201; new doctor can log in | As expected | Pass |
| 2 | Admin audit log | Entries and action list returned | As expected | Pass |
| 3 | Patient sign-up | 201, logged in as patient, password stored hashed | As expected | Pass |
| 4 | Login | 401 wrong password/unknown email; 200 correct | As expected | Pass |
| 5 | Logout | Session ends; /me returns 401 | As expected | Pass |
| 6 | Pharmacist verifies a shared code (lower case) | Items, stock check and total price returned | As expected | Pass |
| 7 | Dispense | Stock 100->40 and 100->70; status filled; DISPENSE audit row | As expected | Pass |
| 8 | Dispense with one item short | 409; no stock changed (all-or-nothing) | As expected | Pass |
| 9 | Two pharmacists dispense the same code at once | Exactly one 200 and one 409; stock reduced once | As expected | Pass |
| 10 | Doctor issues a prescription | 201, unique code, items saved, expiry after issue, audit row | As expected | Pass |
| 11 | Prescription-issued alert | Patient gets an alert with the code, marked simulated (no SMTP) | As expected | Pass |
| 12 | Prescription past its expiry date | Status shows expired | As expected | Pass |
| 13 | Doctor searches patients | Matching patient returned | As expected | Pass |
| 14 | Pharmacist stock list | Own pharmacy only, levels ok/low/out, last-updated time | As expected | Pass |
| 15 | Update quantity and price | Saved in MySQL; STOCK_UPDATE audit row | As expected | Pass |
| 16 | Add catalogue medicine then stock it | 201; duplicate stock line 409 | As expected | Pass |
| 17 | Search 'metformin' from Eldoret CBD | Only in-stock rows, nearest first, out-of-stock pharmacy excluded | As expected | Pass |
| 18 | Search sorted by price | Ascending prices | As expected | Pass |
| 19 | Search accuracy against the stock table | Exactly the pharmacies with stock > 0 | As expected | Pass |
| 20 | Find pharmacies for a prescription | Pharmacies that can fill everything come first | As expected | Pass |
| 21 | Pharmacy list for the map | 4 pharmacies with Eldoret-area coordinates | As expected | Pass |

## Security tests (22)

| # | Test case | Expected result | Actual result | Status |
|---|---|---|---|---|
| 1 | Duplicate licence, bad coordinates, bad time | 409 / 422 | As expected | Pass |
| 2 | Sign-up asking for doctor/pharmacist/admin role | Account is created as patient only | As expected | Pass |
| 3 | Sign-up input validation | 409 duplicate; 422 bad email/password/name; 415 non-JSON | As expected | Pass |
| 4 | 5 failed logins in 15 minutes | 429 on the next attempt | As expected | Pass |
| 5 | API calls without login | 401 on every protected endpoint | As expected | Pass |
| 6 | Patient/doctor/pharmacist calling other roles' endpoints | 403 every time | As expected | Pass |
| 7 | Admin deactivates a logged-in user | Existing session gets 401; new login gets 403 | As expected | Pass |
| 8 | Dispense the same code twice | Second attempt 409; stock not reduced again; cannot re-share | As expected | Pass |
| 9 | Dispense expired / cancelled prescription | 409 with reason | As expected | Pass |
| 10 | 10 wrong codes in 15 minutes | 429 on the next attempt | As expected | Pass |
| 11 | 10 invalid prescriptions (missing/invalid fields) | All rejected (404/422); nothing saved | As expected | Pass |
| 12 | Patient opens another patient's prescription | Not listed; direct request gets 404 | As expected | Pass |
| 13 | Cancelling prescriptions | Other doctor 404; owner 200; second cancel 409 | As expected | Pass |
| 14 | Pharmacy checks a code that was not shared | 404 with 'not shared' message | As expected | Pass |
| 15 | Prescription shared with pharmacy 1 | Pharmacy 1 can open it; pharmacy 2 gets 404 | As expected | Pass |
| 16 | Patient revokes access | Verify and dispense both refused right away; audit row | As expected | Pass |
| 17 | Access window has ended | Pharmacy gets 404 | As expected | Pass |
| 18 | Patient shares/revokes another patient's prescription | 404 | As expected | Pass |
| 19 | Grant longer than 72 h / unknown pharmacy | 422 / 404 | As expected | Pass |
| 20 | Negative quantity, zero/text price | 422 | As expected | Pass |
| 21 | Edit another pharmacy's stock line | 404 | As expected | Pass |
| 22 | Bad search input incl. SQL text | 422 for invalid; SQL text treated as plain text | As expected | Pass |

## System tests (1)

| # | Test case | Expected result | Actual result | Status |
|---|---|---|---|---|
| 1 | Doctor issues -> patient views and searches -> shares -> pharmacist verifies and dispenses | Alert sent, full-coverage pharmacy first, stock falls by prescribed amounts, status filled, every step audited | As expected | Pass |

## API tests with Postman

`postman/PharmaFinder.postman_collection.json` walks the whole journey over HTTP against the running server
(health check, unauthorised access, invalid prescription, prescription creation, alert, search, ranking,
sharing, verification, dispensing, reuse refusal, negative stock, audit log).

Run on 2026-10-30 with Newman (Postman's command-line runner) against a freshly seeded database:
**22 requests, 30 assertions, 0 failed.** Full output: `docs/POSTMAN_RUN.txt`.

To repeat: start the app, reseed (`python -m database.seed`), then import the collection into Postman and
click Run, or run `npx newman run postman/PharmaFinder.postman_collection.json`.
