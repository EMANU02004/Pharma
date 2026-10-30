# Changes from the proposal

The team agreed these scope changes on 30 October 2026. Everything else follows the Group 3 proposal.

## Scope

| Proposal | Now | Reason |
|---|---|---|
| QR code on each prescription | Unique 8-character prescription code (`XXXX-XXXX`) | Simpler to build and test; codes are random (31^8 possibilities), avoid look-alike characters, and code checks are rate-limited |
| QR token invalid after 15 minutes | No separate timer; the code works while the prescription is active and in date | Access is controlled by the patient's grant and single use |
| Digital signature on prescriptions | Not built | Integrity comes from server rules: only the issuing doctor creates it, no endpoint edits items afterwards, and every action is audited. The app makes no signing claim. |
| Tap-to-Hold 2-hour reservations | Dropped | Scope reduced to deliver tested core flows |
| Payment | Not built (also excluded in the proposal) | - |
| Admin verifies doctors and pharmacies | Dropped. Patients sign up themselves; the admin creates doctor and pharmacist accounts ("pre-registered, trusted accounts for the pilot") | Stops anyone registering as a doctor without a verification workflow |
| SMS/email alerts | In-app alert when a prescription is issued or dispensed; email only when SMTP is configured, otherwise marked "simulated" | No SMS gateway credentials |
| QR images stored on disk | Nothing stored on disk | Vercel has no persistent disk |

## Database (proposal section 3.5)

| Change | Why |
|---|---|
| `Reservation` table removed, `notifications` added (still 12 tables) | Reservations dropped; alerts need storage |
| `users.password_hash`, `users.is_active` added | Secure login; admin deactivation |
| `pharmacists.pharmacy_id` added | Limits a pharmacist to their own pharmacy's stock and shared prescriptions |
| `pharmacies.latitude/longitude`, `open_days/opens_at/closes_at` | Map, distance and "open now" need structured data; `is_verified` replaced by `is_active` |
| `medicines.generic_name` added; `prescription` column renamed `requires_prescription` | Search by generic name |
| `item_stock.update` renamed `updated_at`; price stored as `price_kes` | `UPDATE` is a reserved word in MySQL; prices are in KES, not Rwandan francs |
| `patients.sector` renamed `sub_county` | Kenyan administrative unit |
| `prescription_items.frequency` added to the column list | It was in the proposal's example table but missing from the column list |
| `prescriptions.filled_at`, `filled_by_pharmacy_id`, `notes` added | Record who dispensed and when |
| `grant_access.revoked_at` added | Revoking (it was in the class diagram but not the ERD) |
| `doctors.facility` added | Shown to the pharmacist when checking a prescription |

## Claims in the proposal that are **not** implemented

Keep these off the slides unless they are built:

- End-to-end encryption of all data. In production the app uses HTTPS (Vercel) and TLS to the database when `DB_SSL_CA` is set; data at rest is not encrypted by the app.
- Anonymised search queries. Search requests come from logged-in users.
- Account deletion and data export for patients.
- Generic substitution labelling at the pharmacy.
- Live stock sync by webhook from pharmacy systems. Stock is entered in PharmaFinder.
