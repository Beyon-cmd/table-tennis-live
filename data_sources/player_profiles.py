"""Resolve player identities against WTT's public ranking feed on demand."""
from __future__ import annotations

from dataclasses import dataclass
from collections import OrderedDict
import re
import threading
import time
import unicodedata
from urllib.parse import urlparse

import httpx
import httpcore  # Eager-load AnyIO's lazy map before the profile worker thread starts.

from data_sources.name_map import _NAME_MAP
from data_sources.rankings import fetch_rankings

DETAILS_URL = "https://wtt-web-cms-api-prod.azurewebsites.net/api/cms/GetPlayersDataByID"
PHOTO_HOST = "wttsimfiles.blob.core.windows.net"


@dataclass(frozen=True)
class PlayerRequest:
    name: str
    raw: str = ""
    country: str = ""
    player_id: str = ""


def profile_url(player_id: str) -> str:
    return f"https://www.worldtabletennis.com/playerDescription?playerId={player_id}" if re.fullmatch(r"[1-9]\d*", str(player_id or "")) else ""


def split_players(name: str) -> list[str]:
    # Team/doubles names are never used as a single person's identity.
    return [part.strip() for part in re.split(r"\s*/\s*", name or "") if part.strip()]


def clean_name(name: str) -> str:
    return re.sub(r"\s*(?:\([A-Z]{3}\)|\[\d+\])\s*$", "", (name or "").strip()).strip()


def request_from_match(match, index: int) -> PlayerRequest:
    name = match.player_a if index == 0 else match.player_b
    raw = match.player_a_raw if index == 0 else match.player_b_raw
    player_id = match.player_a_id if index == 0 else match.player_b_id
    country = re.search(r"\(([A-Z]{3})\)$", name or "")
    return PlayerRequest(name, raw, country[1] if country else "", player_id)


def _name_key(name: str) -> str:
    name = clean_name(name)
    if name in _NAME_MAP.values():
        matches = [raw for raw, chinese in _NAME_MAP.items() if chinese == name]
        if len(matches) == 1:
            name = matches[0]
    value = unicodedata.normalize("NFKD", name).casefold()
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(sorted(re.findall(r"[a-z0-9]+", value)))


def resolve_from_rows(request: PlayerRequest, rows: dict[str, list[dict]]) -> dict | None:
    requested_id = request.player_id if profile_url(request.player_id) else ""
    target = _name_key(request.raw or request.name)
    country = (request.country or "").upper()
    candidates = []
    for event, entries in rows.items():
        for row in entries:
            rid = str(row.get("IttfId") or "")
            if requested_id:
                if rid != requested_id:
                    continue
            elif not target or _name_key(row.get("PlayerName", "")) != target:
                continue
            row_country = str(row.get("CountryCode") or row.get("AssociationCountryCode") or "").upper()
            if country and row_country and country != row_country:
                continue
            candidates.append((event, row))
    ids = {str(row.get("IttfId") or "") for _, row in candidates}
    if not candidates or len(ids) != 1 or not profile_url(next(iter(ids))):
        return None
    event, row = min(candidates, key=lambda item: int(item[1].get("rank") or item[1].get("CurrentRank") or 999999))
    return {
        "id": str(row["IttfId"]),
        "name": row["PlayerName"],
        "country": row.get("CountryCode") or row.get("AssociationCountryCode") or country,
        "rank": row.get("rank") or row.get("CurrentRank"),
        "points": row.get("points") or row.get("RankingPointsYTD"),
        "event": event,
        "published": row.get("PublishDate") or "",
    }


def parse_player_details(payload: dict, player_id: str) -> dict:
    """Only accept a player record with the exact official ITTF ID."""
    extra = payload.get("additional_data") or {}
    players = extra.get("PlayerData") or []
    if not isinstance(players, list):
        players = [players]
    player = next((p for p in players if str(p.get("IttfId") or "") == player_id), None)
    if not player:
        return {}
    stats = extra.get("StatsData") or []
    if not isinstance(stats, list):
        stats = [stats]
    singles = "WS" if player.get("Gender") == "F" else "MS"
    stat = next((s for s in stats if str(s.get("IttfId") or "") == player_id and s.get("SubeventCode") == singles), {})
    wins, total = stat.get("current_year_total_wins"), stat.get("current_year_total_matches")
    try:
        win_rate = round(100 * int(wins) / int(total)) if int(total) > 0 else None
    except (TypeError, ValueError, ZeroDivisionError):
        win_rate = None
    # Dialog-scale portrait: prefer the official 400px variant over multi-MB 1080px.
    image_url = str(player.get("HeadShot") or player.get("HeadshotR") or "")
    parsed = urlparse(image_url)
    if parsed.scheme != "https" or parsed.hostname != PHOTO_HOST:
        image_url = ""
    return {
        "name": player.get("PlayerName") or payload.get("fullName") or "",
        "country": player.get("CountryCode") or payload.get("orgCode") or "",
        "country_name": player.get("CountryName") or payload.get("countryName") or "",
        "rank": payload.get("ranking"),
        "points": payload.get("rankingPoints"),
        "event": singles,
        "age": player.get("Age") or payload.get("age") or "",
        "hand": player.get("Handedness") or "",
        "grip": player.get("Grip") or "",
        "win_rate": win_rate,
        "year_wins": wins,
        "year_matches": total,
        "image_url": image_url,
        "bio": player.get("Bio") or "",
    }


def fetch_player_details(player_id: str) -> dict:
    if not profile_url(player_id):
        return {}
    response = httpx.get(f"{DETAILS_URL}/{player_id}", timeout=15, follow_redirects=True)
    response.raise_for_status()
    return parse_player_details(response.json(), player_id)


def fetch_profile_photo(image_url: str) -> bytes:
    parsed = urlparse(image_url or "")
    if parsed.scheme != "https" or parsed.hostname != PHOTO_HOST:
        return b""
    try:
        with httpx.stream("GET", image_url, timeout=12, follow_redirects=True) as photo:
            photo.raise_for_status()
            if not photo.headers.get("content-type", "").lower().startswith("image/"):
                return b""
            chunks, size = [], 0
            for chunk in photo.iter_bytes():
                size += len(chunk)
                if size > 2_000_000:
                    return b""
                chunks.append(chunk)
            return b"".join(chunks)
    except (httpx.HTTPError, ValueError):
        return b""


class PlayerProfileService:
    """Small in-memory cache; no player database or photos are stored on disk."""

    def __init__(self):
        self._lock = threading.Lock()
        self._rows = None
        self._loaded_at = 0.0
        self._profiles = OrderedDict()
        self._photos = OrderedDict()

    def resolve(self, request: PlayerRequest, known_rows=None) -> dict:
        fallback = {"id": request.player_id if profile_url(request.player_id) else "", "name": request.raw or clean_name(request.name), "country": request.country, "rank": None, "points": None, "event": "", "published": ""}
        rows = known_rows if known_rows and all(known_rows.values()) else None
        if rows is None and profile_url(request.player_id):
            rows = {"MS": [], "WS": []}  # Direct official ID needs no ranking-name search.
        if rows is None:
            with self._lock:
                if self._rows is None or time.monotonic() - self._loaded_at > 1800:
                    try:
                        self._rows = fetch_rankings()
                        self._loaded_at = time.monotonic()
                    except Exception:
                        if self._rows is None:
                            self._rows = {"MS": [], "WS": []}
                rows = self._rows
        resolved = resolve_from_rows(request, rows) or fallback
        player_id = resolved.get("id")
        if not profile_url(player_id):
            return resolved
        with self._lock:
            cached = self._profiles.get(player_id)
            if cached and time.monotonic() - cached[0] < 900:
                self._profiles.move_to_end(player_id)
                return {**resolved, **cached[1]}
        try:
            details = fetch_player_details(player_id)
        except (httpx.HTTPError, ValueError, TypeError):
            details = {}
        if details:
            with self._lock:
                self._profiles[player_id] = (time.monotonic(), details)
                self._profiles.move_to_end(player_id)
                while len(self._profiles) > 16:
                    self._profiles.popitem(last=False)
        return {**resolved, **details}

    def photo(self, image_url: str) -> bytes:
        with self._lock:
            cached = self._photos.get(image_url)
            if cached:
                self._photos.move_to_end(image_url)
                return cached
        data = fetch_profile_photo(image_url)
        if data:
            with self._lock:
                self._photos[image_url] = data
                self._photos.move_to_end(image_url)
                while len(self._photos) > 16:
                    self._photos.popitem(last=False)
        return data
