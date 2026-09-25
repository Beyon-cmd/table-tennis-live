"""Small standards-compliant iCalendar exporter for scheduled matches."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256

from models import Match, STATUS_UPCOMING

BEIJING = timezone(timedelta(hours=8), "北京时间")


def start_utc(match: Match) -> datetime:
    """Match timestamps are normalized to the viewer's system-local clock."""
    start = match.start_time
    if start.tzinfo is None:
        start = start.astimezone()
    return start.astimezone(timezone.utc)


def time_labels(match: Match) -> str:
    instant = start_utc(match)
    local = instant.astimezone()
    china = instant.astimezone(BEIJING)
    return f"本机时间 {local:%Y-%m-%d %H:%M}  ·  北京时间 {china:%Y-%m-%d %H:%M}"


def _escape(value: str) -> str:
    return (value.replace("\\", "\\\\").replace("\r\n", "\n")
            .replace("\r", "\n").replace("\n", "\\n")
            .replace(";", "\\;").replace(",", "\\,"))


def _fold(line: str) -> list[str]:
    lines, current = [], ""
    for char in line:
        if len((current + char).encode("utf-8")) > 75:
            lines.append(current)
            current = " " + char
        else:
            current += char
    lines.append(current)
    return lines


def build_ics(match: Match, now: datetime | None = None) -> bytes:
    if match.status != STATUS_UPCOMING:
        raise ValueError("只能导出尚未开始的比赛")
    start = start_utc(match)
    # Duration is a calendar placeholder; the actual finish is not available.
    end = start + timedelta(hours=3 if "团体" in match.competition else 2)
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    uid = sha256(match.id.encode("utf-8")).hexdigest()[:24] + "@tabletennislive.local"
    title = f"{match.player_a} vs {match.player_b} · {match.competition}"
    description = (f"{time_labels(match)}\n"
                   "开始时间来自当前赛程；结束时间仅为日历占位，实际赛程可能调整。")
    fields = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Table Tennis Live//Match Calendar//ZH",
        "CALSCALE:GREGORIAN", "BEGIN:VEVENT", f"UID:{uid}",
        f"DTSTAMP:{stamp:%Y%m%dT%H%M%SZ}",
        f"DTSTART:{start:%Y%m%dT%H%M%SZ}", f"DTEND:{end:%Y%m%dT%H%M%SZ}",
        f"SUMMARY:{_escape(title)}", f"DESCRIPTION:{_escape(description)}",
        "END:VEVENT", "END:VCALENDAR",
    ]
    return ("\r\n".join(part for line in fields for part in _fold(line)) + "\r\n").encode("utf-8")
