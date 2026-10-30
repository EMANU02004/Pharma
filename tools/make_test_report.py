"""Run the pytest suite and write docs/TEST_REPORT.md from the real results.

Usage:  python tools/make_test_report.py
The "Actual" column comes from this run - nothing is filled in by hand.
"""
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XML = os.path.join(ROOT, ".pytest_cache", "report.xml")
OUT = os.path.join(ROOT, "docs", "TEST_REPORT.md")

# test name -> (type, what is checked, expected result)
CASES = {
    "test_haversine_zero_distance": ("Unit", "Distance from a point to itself", "0 km"),
    "test_haversine_known_distance_eldoret_to_nairobi": ("Unit", "Haversine distance Eldoret to Nairobi", "About 263 km (+/- 5)"),
    "test_parse_days_ranges_and_lists": ("Unit", "Opening-day parsing (Mon-Sat, Mon-Fri,Sun, Daily, Fri-Mon)", "Correct weekday sets"),
    "test_is_open_respects_days_and_hours": ("Unit", "Open-now check by day and time", "Open Wed 10:00; closed Wed 21:00 and Sunday"),
    "test_ranking_full_coverage_beats_closer_partial": ("Unit", "Prescription ranking algorithm", "Full coverage first, then distance"),
    "test_generated_codes_are_well_formed_and_unique": ("Unit", "2,000 generated prescription codes", "All XXXX-XXXX, unambiguous alphabet, no duplicates"),
    "test_normalise_code_accepts_messy_input_and_rejects_bad": ("Unit", "Code normalisation", "Lower case/spaces accepted; wrong length, O/1 and SQL text rejected"),
    "test_password_hashing_is_salted_and_verifiable": ("Unit", "Password hashing", "Different salted hashes; correct password verifies, wrong one fails"),
    "test_weak_passwords_rejected": ("Unit", "Weak password rules", "Rejected"),
    "test_as_int_rejects_bad_quantities": ("Unit", "Quantity validation", "Negative, text, decimal, boolean rejected"),
    "test_as_price_rejects_invalid": ("Unit", "Price validation", "Zero, negative, text rejected"),
    "test_register_creates_patient_and_logs_in": ("Integration", "Patient sign-up", "201, logged in as patient, password stored hashed"),
    "test_register_cannot_choose_doctor_or_admin_role": ("Security", "Sign-up asking for doctor/pharmacist/admin role", "Account is created as patient only"),
    "test_register_rejects_duplicate_email_and_bad_input": ("Security", "Sign-up input validation", "409 duplicate; 422 bad email/password/name; 415 non-JSON"),
    "test_login_success_and_failure": ("Integration", "Login", "401 wrong password/unknown email; 200 correct"),
    "test_login_is_rate_limited_after_repeated_failures": ("Security", "5 failed logins in 15 minutes", "429 on the next attempt"),
    "test_logout_ends_session": ("Integration", "Logout", "Session ends; /me returns 401"),
    "test_protected_endpoints_require_login": ("Security", "API calls without login", "401 on every protected endpoint"),
    "test_cross_role_access_is_forbidden": ("Security", "Patient/doctor/pharmacist calling other roles' endpoints", "403 every time"),
    "test_deactivated_user_loses_access_immediately": ("Security", "Admin deactivates a logged-in user", "Existing session gets 401; new login gets 403"),
    "test_doctor_creates_prescription_with_code_and_expiry": ("Integration", "Doctor issues a prescription", "201, unique code, items saved, expiry after issue, audit row"),
    "test_prescription_issue_alert_reaches_patient": ("Integration", "Prescription-issued alert", "Patient gets an alert with the code, marked simulated (no SMTP)"),
    "test_prescription_with_missing_fields_is_rejected": ("Security", "10 invalid prescriptions (missing/invalid fields)", "All rejected (404/422); nothing saved"),
    "test_patient_sees_only_own_prescriptions": ("Security", "Patient opens another patient's prescription", "Not listed; direct request gets 404"),
    "test_doctor_cancels_only_own_active_prescription": ("Security", "Cancelling prescriptions", "Other doctor 404; owner 200; second cancel 409"),
    "test_overdue_prescription_becomes_expired": ("Integration", "Prescription past its expiry date", "Status shows expired"),
    "test_doctor_patient_search": ("Integration", "Doctor searches patients", "Matching patient returned"),
    "test_unshared_prescription_cannot_be_opened_by_pharmacy": ("Security", "Pharmacy checks a code that was not shared", "404 with 'not shared' message"),
    "test_shared_prescription_opens_only_at_that_pharmacy": ("Security", "Prescription shared with pharmacy 1", "Pharmacy 1 can open it; pharmacy 2 gets 404"),
    "test_revoked_access_blocks_pharmacy_immediately": ("Security", "Patient revokes access", "Verify and dispense both refused right away; audit row"),
    "test_expired_access_blocks_pharmacy": ("Security", "Access window has ended", "Pharmacy gets 404"),
    "test_patient_cannot_share_or_revoke_someone_elses_prescription": ("Security", "Patient shares/revokes another patient's prescription", "404"),
    "test_grant_duration_is_limited": ("Security", "Grant longer than 72 h / unknown pharmacy", "422 / 404"),
    "test_pharmacist_sees_own_stock_with_levels": ("Integration", "Pharmacist stock list", "Own pharmacy only, levels ok/low/out, last-updated time"),
    "test_update_stock_and_price_is_saved_and_audited": ("Integration", "Update quantity and price", "Saved in MySQL; STOCK_UPDATE audit row"),
    "test_negative_stock_and_invalid_price_rejected": ("Security", "Negative quantity, zero/text price", "422"),
    "test_pharmacist_cannot_edit_another_pharmacys_stock": ("Security", "Edit another pharmacy's stock line", "404"),
    "test_add_new_medicine_and_stock_line": ("Integration", "Add catalogue medicine then stock it", "201; duplicate stock line 409"),
    "test_search_by_generic_name_returns_only_in_stock_sorted_by_distance": ("Integration", "Search 'metformin' from Eldoret CBD", "Only in-stock rows, nearest first, out-of-stock pharmacy excluded"),
    "test_search_sort_by_price": ("Integration", "Search sorted by price", "Ascending prices"),
    "test_search_matches_stock_table_exactly": ("Integration", "Search accuracy against the stock table", "Exactly the pharmacies with stock > 0"),
    "test_search_input_validation": ("Security", "Bad search input incl. SQL text", "422 for invalid; SQL text treated as plain text"),
    "test_prescription_pharmacy_ranking_puts_full_coverage_first": ("Integration", "Find pharmacies for a prescription", "Pharmacies that can fill everything come first"),
    "test_pharmacy_list_has_coordinates_for_map": ("Integration", "Pharmacy list for the map", "4 pharmacies with Eldoret-area coordinates"),
    "test_verify_shows_items_stock_and_price": ("Integration", "Pharmacist verifies a shared code (lower case)", "Items, stock check and total price returned"),
    "test_dispense_lowers_stock_and_fills_prescription": ("Integration", "Dispense", "Stock 100->40 and 100->70; status filled; DISPENSE audit row"),
    "test_code_cannot_be_used_twice": ("Security", "Dispense the same code twice", "Second attempt 409; stock not reduced again; cannot re-share"),
    "test_insufficient_stock_changes_nothing": ("Integration", "Dispense with one item short", "409; no stock changed (all-or-nothing)"),
    "test_expired_and_cancelled_prescriptions_cannot_be_dispensed": ("Security", "Dispense expired / cancelled prescription", "409 with reason"),
    "test_code_guessing_is_rate_limited": ("Security", "10 wrong codes in 15 minutes", "429 on the next attempt"),
    "test_concurrent_dispense_fills_exactly_once": ("Integration", "Two pharmacists dispense the same code at once", "Exactly one 200 and one 409; stock reduced once"),
    "test_admin_creates_pharmacy_and_staff_who_can_log_in": ("Integration", "Admin creates pharmacy, pharmacist and doctor", "All 201; new doctor can log in"),
    "test_admin_input_validation_and_duplicates": ("Security", "Duplicate licence, bad coordinates, bad time", "409 / 422"),
    "test_audit_log_lists_actions": ("Integration", "Admin audit log", "Entries and action list returned"),
    "test_full_journey": ("System", "Doctor issues -> patient views and searches -> shares -> pharmacist verifies and dispenses",
                          "Alert sent, full-coverage pharmacy first, stock falls by prescribed amounts, status filled, every step audited"),
}


def main():
    os.makedirs(os.path.dirname(XML), exist_ok=True)
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", f"--junitxml={XML}"], cwd=ROOT,
                          capture_output=True, text=True)
    summary = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "no output"
    tree = ET.parse(XML)
    rows, counts = [], {"Pass": 0, "Fail": 0}
    for case in tree.iter("testcase"):
        name = case.get("name")
        base = name.split("[")[0]
        kind, what, expected = CASES.get(base, ("Other", base, "-"))
        failed = case.find("failure") is not None or case.find("error") is not None
        status = "Fail" if failed else "Pass"
        counts[status] += 1
        actual = "As expected" if not failed else (case.find("failure") or case.find("error")).get("message", "")[:120]
        param = name[len(base):]
        rows.append((kind, what + (f" `{param}`" if param else ""), expected, actual, status, case.get("time")))

    order = {"Unit": 0, "Integration": 1, "Security": 2, "System": 3, "Other": 4}
    rows.sort(key=lambda r: order[r[0]])
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("# PharmaFinder test report\n\n")
        fh.write(f"Generated {datetime.now():%Y-%m-%d %H:%M} by `tools/make_test_report.py` from a real pytest run "
                 "against a MySQL-compatible database rebuilt from `database/schema.sql` and seed data before each test.\n\n")
        fh.write(f"**Result: {counts['Pass']} passed, {counts['Fail']} failed** (pytest: `{summary}`)\n\n")
        for kind in ("Unit", "Integration", "Security", "System", "Other"):
            group = [r for r in rows if r[0] == kind]
            if not group:
                continue
            fh.write(f"## {kind} tests ({len(group)})\n\n| # | Test case | Expected result | Actual result | Status |\n|---|---|---|---|---|\n")
            for i, r in enumerate(group, 1):
                fh.write(f"| {i} | {r[1]} | {r[2]} | {r[3]} | {r[4]} |\n")
            fh.write("\n")
    print(f"{summary}\nWrote {OUT}")
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
