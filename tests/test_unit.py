"""Unit tests for pure logic: distance, opening hours, ranking, codes, validation."""
from datetime import datetime

import pytest

from pharmafinder.errors import ApiError
from pharmafinder.geo import haversine_km, is_open, parse_days, rank_prescription_matches
from pharmafinder.rx import CODE_ALPHABET, generate_code, normalise_code
from pharmafinder.security import hash_password, verify_password
from pharmafinder.validation import as_int, as_password, as_price


def test_haversine_zero_distance():
    assert haversine_km(0.5143, 35.2698, 0.5143, 35.2698) == pytest.approx(0, abs=1e-9)


def test_haversine_known_distance_eldoret_to_nairobi():
    # Eldoret (0.5143, 35.2698) to Nairobi (-1.2921, 36.8219) is about 263 km in a straight line
    assert haversine_km(0.5143, 35.2698, -1.2921, 36.8219) == pytest.approx(263, abs=5)


def test_parse_days_ranges_and_lists():
    assert parse_days("Mon-Sat") == {0, 1, 2, 3, 4, 5}
    assert parse_days("Mon-Fri,Sun") == {0, 1, 2, 3, 4, 6}
    assert parse_days("Daily") == set(range(7))
    assert parse_days("Fri-Mon") == {4, 5, 6, 0}


def test_is_open_respects_days_and_hours():
    wed_10am = datetime(2026, 10, 28, 10, 0)
    wed_9pm = datetime(2026, 10, 28, 21, 0)
    sunday = datetime(2026, 11, 1, 10, 0)
    assert is_open("Mon-Sat", "08:00", "20:00", now=wed_10am)
    assert not is_open("Mon-Sat", "08:00", "20:00", now=wed_9pm)
    assert not is_open("Mon-Sat", "08:00", "20:00", now=sunday)


def test_ranking_full_coverage_beats_closer_partial():
    pharmacies = [
        {"name": "near-partial", "items_available": 1, "distance_km": 0.5, "total_price_kes": 100},
        {"name": "far-full", "items_available": 2, "distance_km": 5.0, "total_price_kes": 500},
        {"name": "near-full", "items_available": 2, "distance_km": 1.0, "total_price_kes": 900},
    ]
    ranked = [p["name"] for p in rank_prescription_matches(pharmacies, needed_count=2)]
    assert ranked == ["near-full", "far-full", "near-partial"]


def test_generated_codes_are_well_formed_and_unique():
    codes = {generate_code() for _ in range(2000)}
    assert len(codes) == 2000
    for code in codes:
        assert len(code) == 9 and code[4] == "-"
        assert all(ch in CODE_ALPHABET for ch in code.replace("-", ""))


def test_normalise_code_accepts_messy_input_and_rejects_bad():
    assert normalise_code(" pf7k aaa2 ") == "PF7K-AAA2"
    assert normalise_code("PF7K-AAA2") == "PF7K-AAA2"
    assert normalise_code("PF7K-AAA") is None
    assert normalise_code("PF7K-AAO1") is None  # O and 1 are not in the alphabet
    assert normalise_code("'; DROP TABLE x;--") is None


def test_password_hashing_is_salted_and_verifiable():
    h1, h2 = hash_password("Secret123"), hash_password("Secret123")
    assert h1 != h2 and "Secret123" not in h1
    assert verify_password(h1, "Secret123")
    assert not verify_password(h1, "secret123")


@pytest.mark.parametrize("value", ["short1", "allletters", "12345678", None, 123])
def test_weak_passwords_rejected(value):
    with pytest.raises(ApiError):
        as_password(value)


@pytest.mark.parametrize("value", [-1, "abc", 1.5, True, None])
def test_as_int_rejects_bad_quantities(value):
    with pytest.raises(ApiError):
        as_int(value, "quantity", 0)


@pytest.mark.parametrize("value", [0, -5, "free", None])
def test_as_price_rejects_invalid(value):
    with pytest.raises(ApiError):
        as_price(value)
