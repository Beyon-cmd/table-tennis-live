"""WTT venue-local clock conversion.

WTT's event feed exposes ``timeZoneId``; its website frontend publishes the
matching fixed UTC offset codes. The event ID selects the offset in force for
that event (for example, Montpellier 2024 UTC+2 and 2026 UTC+1). Unknown IDs
are never treated as the computer's timezone.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

_OFFSET_IDS = {
    -720: "3", -660: "4", -600: "5", -540: "6", -480: "7 9",
    -420: "8 10 11 12", -360: "13 14 15 16", -300: "17 18 19",
    -270: "20", -240: "21 22 23 24 25", -210: "26",
    -180: "27 28 29 30 31 32", -120: "33 34", -60: "35 36",
    0: "37 38 39 41 42", 60: "40 43 44 45 46 47 48",
    120: "49 50 51 52 53 54 55 57 58 61",
    180: "56 59 60 62 63 64", 210: "66",
    240: "65 67 68 69 70 71", 270: "72",
    300: "73 74 75", 330: "76 77", 345: "78",
    360: "79 80", 390: "81", 420: "82 83",
    480: "84 85 86 87 88 89 90", 540: "91 92 99",
    570: "93 94", 600: "95 96 97 98", 660: "100 101",
    720: "102 103 104 105 106", 780: "107 108",
}
OFFSET_MINUTES_BY_ID = {
    int(zone_id): minutes for minutes, ids in _OFFSET_IDS.items() for zone_id in ids.split()
}


def offset_for_event(event_row: dict) -> timedelta | None:
    try:
        minutes = OFFSET_MINUTES_BY_ID.get(int(event_row.get("timeZoneId")))
    except (TypeError, ValueError):
        return None
    return timedelta(minutes=minutes) if minutes is not None else None


def venue_to_local(value: datetime, offset: timedelta) -> datetime:
    """Convert WTT venue-local wall time to this computer's local wall time."""
    aware = value if value.tzinfo else value.replace(tzinfo=timezone(offset))
    return aware.astimezone().replace(tzinfo=None)
