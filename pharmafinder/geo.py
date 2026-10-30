"""Distance, opening-hours and ranking algorithms used by pharmacy search."""
import math
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

EARTH_RADIUS_KM = 6371.0088
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance between two points in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def parse_days(open_days):
    """'Mon-Sat' -> {0..5}; 'Mon-Fri,Sun' -> {0..4, 6}; 'Daily' -> all days."""
    spec = (open_days or "").strip()
    if spec.lower() in ("daily", "mon-sun", "everyday"):
        return set(range(7))
    days = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = (p.strip()[:3].title() for p in part.split("-", 1))
            i, j = DAY_NAMES.index(start), DAY_NAMES.index(end)
            k = i
            while True:
                days.add(k)
                if k == j:
                    break
                k = (k + 1) % 7
        else:
            days.add(DAY_NAMES.index(part[:3].title()))
    return days


def _as_time(value):
    if isinstance(value, time):
        return value
    if isinstance(value, timedelta):  # PyMySQL returns TIME columns as timedelta
        secs = int(value.total_seconds())
        return time(secs // 3600 % 24, secs % 3600 // 60)
    h, m, *_ = str(value).split(":")
    return time(int(h), int(m))


def is_open(open_days, opens_at, closes_at, now=None, tz="Africa/Nairobi"):
    now = now or datetime.now(ZoneInfo(tz))
    if now.weekday() not in parse_days(open_days):
        return False
    start, end = _as_time(opens_at), _as_time(closes_at)
    current = now.time().replace(second=0, microsecond=0)
    if start <= end:
        return start <= current < end
    return current >= start or current < end  # opening hours that cross midnight


def format_time(value):
    return _as_time(value).strftime("%H:%M")


SORT_KEYS = {
    "distance": lambda r: (r["distance_km"] is None, r["distance_km"] or 0, r["price_kes"] or 0),
    "price": lambda r: (r["price_kes"] is None, r["price_kes"] or 0, r["distance_km"] or 0),
    "stock": lambda r: (-(r["quantity"] or 0), r["distance_km"] or 0),
}


def rank_prescription_matches(pharmacies, needed_count):
    """Order pharmacies for a prescription search.

    1. Pharmacies that can fill every item come first.
    2. Then those covering more items.
    3. Ties broken by distance, then by total price of the items they can supply.
    """
    def key(p):
        full = p["items_available"] == needed_count
        return (
            0 if full else 1,
            -p["items_available"],
            p["distance_km"] if p["distance_km"] is not None else float("inf"),
            p["total_price_kes"],
        )
    return sorted(pharmacies, key=key)
