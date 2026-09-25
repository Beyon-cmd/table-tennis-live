"""2026 爱知·名古屋亚运会乒乓球官方成绩系统。

成绩以官方发布时间为准。赛程列表提供总比分与逐局分；团体赛的
单场对阵由按需加载的 results 接口提供，不推测缺失的分数。
"""
from __future__ import annotations

import json
import time
import zlib
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

import httpx

from data_sources.name_map import to_chinese_name
from models import Game, Match, STATUS_FINISHED, STATUS_LIVE, STATUS_UPCOMING


BASE = "https://back.results.asiangames2026.org/s/AG2026/en/TTE"
JST = timezone(timedelta(hours=9))
FIRST_DAY = date(2026, 9, 20)
LAST_DAY = date(2026, 9, 28)
EVENT_NAMES = {
    "Men's Singles": "男子单打", "Women's Singles": "女子单打",
    "Men's Doubles": "男子双打", "Women's Doubles": "女子双打",
    "Mixed Doubles": "混合双打", "Men's Team": "男子团体",
    "Women's Team": "女子团体",
}
COUNTRIES = {
    "CHN": "中国", "JPN": "日本", "KOR": "韩国", "PRK": "朝鲜",
    "HKG": "中国香港", "MAC": "中国澳门", "TPE": "中国台北",
    "IND": "印度", "SGP": "新加坡", "THA": "泰国", "MAS": "马来西亚",
    "VIE": "越南", "KAZ": "哈萨克斯坦", "IRI": "伊朗",
}


def _official_json(response: httpx.Response) -> object:
    """官方 CDN 有时把 zlib 字节按 Latin-1 字符再次编码为 UTF-8。"""
    response.raise_for_status()
    raw = response.content
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return json.loads(zlib.decompress(raw.decode("utf-8").encode("latin-1")))


def _number(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _name(side: dict, team: bool) -> tuple[str, str]:
    raw = str(side.get("Name") or "").strip()
    if team:
        return COUNTRIES.get(str(side.get("Org") or ""), raw), raw
    return to_chinese_name(raw) or raw, raw


def _sets(home: dict, away: dict) -> tuple[list[tuple[int, int]], tuple[int, int] | None]:
    pairs = []
    current = None
    for left, right in zip(home.get("Splits") or [], away.get("Splits") or []):
        if left.get("Res") in (None, "") or right.get("Res") in (None, ""):
            continue
        pair = (_number(left["Res"]), _number(right["Res"]))
        # 11 分制：10 平后须领先 2 分。未完成的一局不能当作已结束。
        if max(pair) >= 11 and abs(pair[0] - pair[1]) >= 2:
            pairs.append(pair)
        else:
            current = pair
            break  # 后面的局不能越过尚未结束的这一局
    return pairs, current


def parse_schedule(row: dict, now: datetime | None = None) -> Match | None:
    """把官方每日赛程条目转成应用模型。"""
    if not isinstance(row, dict) or row.get("IsPhase") or not row.get("Key"):
        return None
    home, away = row.get("Home") or {}, row.get("Away") or {}
    if not home.get("Name") or not away.get("Name"):
        return None
    try:
        start = datetime.fromisoformat(row["DateTimeRaw"]).astimezone().replace(tzinfo=None)
    except (KeyError, TypeError, ValueError):
        return None
    now = now or datetime.now()
    state = str(row.get("Status") or "").upper()
    status = (STATUS_LIVE if row.get("IsLive") or state in {"LIVE", "RUNNING", "IN_PROGRESS"}
              else STATUS_FINISHED if state in {"OFFICIAL", "UNOFFICIAL", "FINISHED", "COMPLETED"}
              else STATUS_UPCOMING)
    team = row.get("Type") == "T" or ".TEAM" in str(row.get("Event") or "")
    name_a, raw_a = _name(home, team)
    name_b, raw_b = _name(away, team)
    sets, current = _sets(home, away) if not team else ([], None)
    if status != STATUS_LIVE:
        current = None
    score_known = bool(home.get("Result") not in (None, "") and away.get("Result") not in (None, ""))
    score_a, score_b = _number(home.get("Result")), _number(away.get("Result"))
    score_reconciled = False
    if status != STATUS_UPCOMING and not team and sets:
        completed_a = sum(a > b for a, b in sets)
        completed_b = sum(b > a for a, b in sets)
        # 官方 Splits 已写出完整局分，但 Result 总局数仍是上一轮轮询值时，
        # 优先显示由已结束局分直接算出的总比分；反向滞后则保留官方 Result。
        if completed_a + completed_b > score_a + score_b:
            score_a, score_b = completed_a, completed_b
            score_known = True
            score_reconciled = True
    return Match(
        id=f"asiangames:{row['Key']}", source="majors",
        competition=f"2026 爱知·名古屋亚运会 · {EVENT_NAMES.get(row.get('EventDesc'), row.get('EventDesc') or '乒乓球')} · {row.get('PhaseDescA') or ''}",
        status=status, start_time=start, player_a=name_a, player_b=name_b,
        player_a_raw=raw_a, player_b_raw=raw_b,
        score_a=score_a, score_b=score_b,
        sets=sets, current_set=current, score_known=score_known,
        score_reconciled=score_reconciled,
        last_update=now,
    )


def apply_team_detail(match: Match, payload: dict) -> Match:
    """用官方 SubUnits 填充团体赛的单场对阵、局分。"""
    games = []
    for unit in payload.get("SubUnits") or []:
        competitors = unit.get("Competitors") or []
        if len(competitors) < 2:
            continue
        sides = {str(c.get("Org")): c for c in competitors}
        home_org = str((payload.get("Competitors") or [{}])[0].get("Org") or "")
        left = sides.get(home_org, competitors[0])
        right = next((c for c in competitors if c is not left), competitors[1])
        periods = (unit.get("Results") or {}).get("Periods") or []
        sets = [(_number(p.get("ResHome")), _number(p.get("ResAway")))
                for p in periods if p.get("ResHome") not in (None, "")
                and p.get("ResAway") not in (None, "")
                and (_number(p.get("ResHome")) or _number(p.get("ResAway")))]
        games.append(Game(
            player_a=to_chinese_name(left.get("Name") or "") or left.get("Name") or "",
            player_b=to_chinese_name(right.get("Name") or "") or right.get("Name") or "",
            score_a=_number(left.get("Result")), score_b=_number(right.get("Result")),
            sets=sets,
        ))
    match.games = games
    return match


class AsianGamesFeed:
    """短时内存缓存，避免轮询多个日期时反复请求官方接口。"""

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://results.asiangames2026.org/", "Accept-Encoding": "identity"},
            timeout=12.0, follow_redirects=True,
        )
        self._cache: dict[date, tuple[float, list[Match]]] = {}

    def matches(self) -> list[Match]:
        today = datetime.now(JST).date()
        if today < FIRST_DAY - timedelta(days=1) or today > LAST_DAY + timedelta(days=1):
            return []
        result: list[Match] = []
        for day in (today - timedelta(days=1), today, today + timedelta(days=1)):
            if not FIRST_DAY <= day <= LAST_DAY:
                continue
            cached = self._cache.get(day)
            ttl = (2 if cached and any(m.status == STATUS_LIVE for m in cached[1])
                   else 8) if day == today else 90
            if cached and time.monotonic() - cached[0] < ttl:
                result.extend(cached[1])
                continue
            try:
                response = self.client.get(f"{BASE}/schedule/daily/{day.isoformat()}")
                payload = _official_json(response)
                if not isinstance(payload, list):
                    raise ValueError("官方赛程格式异常")
                matches = [match for row in payload if (match := parse_schedule(row))]
                self._cache[day] = (time.monotonic(), matches)
                result.extend(matches)
            except (httpx.HTTPError, ValueError, UnicodeError, zlib.error):
                if cached:
                    result.extend(replace(match, data_stale=True) for match in cached[1])
                else:
                    raise
        return result

    def detail(self, match: Match) -> Match:
        if "团体" not in match.competition:
            return match
        key = match.id.removeprefix("asiangames:")
        payload = _official_json(self.client.get(f"{BASE}/results/{quote(key, safe='.-_')}"))
        if isinstance(payload, dict):
            return apply_team_detail(match, payload)
        return match
