"""德国 TTBL 数据源（来源：ttbl.de 官网）。

赛程通过官网自用的 Next.js 公开数据接口获取：
_next/data/{buildId}/de/bundesliga/gameschedule/current/current/all.json
（“current”会 307 重定向到当前赛季/轮次）。

单场小比分（每场对阵选手 + 每局比分）来自官网比赛详情页：
_next/data/{buildId}/de/bundesliga/gameday/{赛季}/{轮次}/{比赛ID}.json
最近 6 场已结束比赛预热，其余在打开详情时按需抓取。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from data_sources.base import DataSource, make_client
from data_sources.name_map import to_chinese_name, to_chinese_team
from models import Game, Match, STATUS_FINISHED, STATUS_LIVE, STATUS_UPCOMING

BASE = "https://www.ttbl.de"
HOME_URL = f"{BASE}/"
SCHEDULE_DATA = (
    f"{BASE}/_next/data/{{build_id}}/de/bundesliga/gameschedule/current/current/all.json"
)


class TTBLDataSource(DataSource):
    name = "TTBL"

    def __init__(self):
        self._client = make_client()
        self._build_id: str | None = None
        self._build_id_ts = 0.0
        self._home_rows: list[dict] = []
        self._home_season: dict = {}
        self._rows: list[dict] = []
        self._rows_ts = 0.0
        self._row_by_id: dict[str, dict] = {}
        self._games_cache: dict[str, tuple[list[Game], float]] = {}

    # ---------------- 对外接口 ----------------
    def get_matches(self) -> list[Match]:
        rows = self._fetch_schedule()
        now = datetime.now()
        matches: list[Match] = []
        finished: list[Match] = []
        for row in rows:
            match = self._build_match(row, now)
            if match is not None:
                matches.append(match)
                if match.status == STATUS_FINISHED:
                    finished.append(match)
                elif match.status == STATUS_LIVE:
                    match.games = self._get_match_games(match.id)
        # 预热最近 4 场已结束比赛的单场比分（缓存 1 小时）
        finished.sort(key=lambda m: m.start_time, reverse=True)
        for match in finished[:4]:
            match.games = self._get_match_games(match.id)
        return matches

    def get_live_matches(self) -> list[Match]:
        return [m for m in self.get_matches() if m.status == STATUS_LIVE]

    def get_schedule(self) -> list[Match]:
        return [m for m in self.get_matches() if m.status != STATUS_LIVE]

    def get_match_detail(self, match_id: str) -> Match | None:
        row = self._row_by_id.get(match_id.removeprefix("ttbl:"))
        if row is None:
            return None
        match = self._build_match(row, datetime.now())
        if match is not None:
            match.games = self._get_match_games(match_id)
        return match

    # ---------------- 数据抓取 ----------------
    def _fetch_schedule(self) -> list[dict]:
        now_ts = datetime.now().timestamp()
        if self._rows and now_ts - self._rows_ts < 2:
            return self._rows
        build_id = self._get_build_id()
        url = SCHEDULE_DATA.format(build_id=build_id)
        response = self._client.get(url)
        response.raise_for_status()
        data = response.json()
        redirect = (data.get("pageProps") or {}).get("__N_REDIRECT") or ""
        if redirect:
            url = f"{BASE}/_next/data/{build_id}{redirect}.json"
            response = self._client.get(url)
            response.raise_for_status()
            data = response.json()
        rows = (data.get("pageProps") or {}).get("matches") or []
        # current/current 只覆盖官网定义的“当前轮”。首页 currentMatches 还
        # 保留刚结束的比赛及 homeGames/awayGames（团体大比分），合并后打开
        # 程序即可显示最近赛果，详情页再按需取逐场/逐局小比分。
        by_id = {str(row.get("id")): row for row in rows if row.get("id")}
        for row in self._home_rows:
            if not row.get("id"):
                continue
            # 首页卡片省略赛季对象；补上它才能拼出详情页 URL。
            row = dict(row)
            row.setdefault("season", self._home_season)
            by_id.setdefault(str(row["id"]), row)
        rows = list(by_id.values())
        self._rows = rows
        self._rows_ts = now_ts
        self._row_by_id = {str(row.get("id")): row for row in rows if row.get("id")}
        return rows

    def _get_build_id(self) -> str:
        now_ts = datetime.now().timestamp()
        if self._build_id and now_ts - self._build_id_ts < 3600:
            return self._build_id
        response = self._client.get(HOME_URL)
        response.raise_for_status()
        m = re.search(
            r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>',
            response.text,
            re.DOTALL,
        )
        if not m:
            raise ValueError("TTBL 首页没有 __NEXT_DATA__")
        page = json.loads(m.group(1)) or {}
        build_id = page.get("buildId")
        if not build_id:
            raise ValueError("TTBL 首页没有 buildId")
        self._build_id = build_id
        self._build_id_ts = now_ts
        self._home_rows = (
            ((page.get("props") or {}).get("pageProps") or {}).get("currentMatches")
            or []
        )
        self._home_season = (
            ((page.get("props") or {}).get("pageProps") or {}).get("season")
            or {}
        )
        return build_id

    def _get_match_games(self, match_id: str) -> list[Game]:
        """比赛详情页里的单场对阵与小比分（缓存 1 小时）。"""
        item = self._games_cache.get(match_id)
        now_ts = datetime.now().timestamp()
        row = self._row_by_id.get(match_id.removeprefix("ttbl:"))
        match = self._build_match(row, datetime.now()) if row else None
        ttl = 3600 if match and match.status == STATUS_FINISHED else 2
        if item is not None and now_ts - item[1] < ttl:
            return item[0]
        games: list[Game] = []
        row = self._row_by_id.get(match_id.removeprefix("ttbl:"))
        if row:
            season = row.get("season") or {}
            gameday = row.get("gameday") or {}
            season_str = f"{season.get('startYear')}-{season.get('endYear')}"
            gameday_index = gameday.get("index")
            if season_str.startswith("-") or gameday_index is None:
                return []
            url = (
                f"{BASE}/_next/data/{self._get_build_id()}/de/bundesliga/gameday/"
                f"{season_str}/{gameday_index}/{match_id.removeprefix('ttbl:')}.json"
            )
            try:
                response = self._client.get(url)
                response.raise_for_status()
                data = response.json()
                sm = (data.get("pageProps") or {}).get("selectedMatch") or {}
                games = self._parse_games(sm)
            except Exception:
                games = []
        self._games_cache[match_id] = (games, now_ts)
        return games

    # ---------------- 解析 ----------------
    @staticmethod
    def _build_match(row: dict, now: datetime) -> Match | None:
        state = row.get("matchState") or ""
        if state == "Inactive":
            return None
        home = (row.get("homeTeam") or {}).get("seasonTeam") or {}
        away = (row.get("awayTeam") or {}).get("seasonTeam") or {}
        home_raw = home.get("name")
        away_raw = away.get("name")
        if not home_raw or not away_raw:
            return None
        home_name = to_chinese_team(home_raw) or home_raw
        away_name = to_chinese_team(away_raw) or away_raw
        try:
            start = datetime.fromtimestamp(int(row["timeStamp"]))
        except (KeyError, ValueError, TypeError):
            return None

        gameday = row.get("gameday") or {}
        competition = f"德国 TTBL · {gameday.get('name') or 'Bundesliga'}"

        home_games = int(row.get("homeGames") or 0)
        away_games = int(row.get("awayGames") or 0)
        has_score = home_games > 0 or away_games > 0

        if state == "Finished":
            status = STATUS_FINISHED
        elif has_score:
            status = STATUS_LIVE
        elif start > now - timedelta(minutes=30):
            status = STATUS_UPCOMING
        else:
            return None

        return Match(
            id=f"ttbl:{row.get('id') or start.timestamp()}",
            source="TTBL",
            competition=competition,
            status=status,
            start_time=start,
            player_a=home_name,
            player_b=away_name,
            player_a_raw="" if home_name == home_raw else home_raw,
            player_b_raw="" if away_name == away_raw else away_raw,
            score_a=home_games,
            score_b=away_games,
            score_known=has_score or status == STATUS_FINISHED,
            last_update=now,
        )

    @staticmethod
    def _parse_games(selected_match: dict) -> list[Game]:
        games: list[Game] = []
        for g in (selected_match.get("games") or []):
            home = TTBLDataSource._player_name(g.get("homePlayer"), g.get("homeDouble"))
            away = TTBLDataSource._player_name(g.get("awayPlayer"), g.get("awayDouble"))
            if not home or not away:
                continue
            sets: list[tuple[int, int]] = []
            for i in range(1, 6):
                a = g.get(f"set{i}HomeScore")
                b = g.get(f"set{i}AwayScore")
                if a is not None and b is not None and (int(a) > 0 or int(b) > 0):
                    sets.append((int(a), int(b)))
            if not sets:
                continue
            games.append(
                Game(
                    player_a=home,
                    player_b=away,
                    score_a=int(g.get("homeSets") or 0),
                    score_b=int(g.get("awaySets") or 0),
                    sets=sets,
                )
            )
        return games

    @staticmethod
    def _player_name(player: dict | None, double: dict | None) -> str:
        def one(p: dict | None) -> str:
            if not p:
                return ""
            first = (p.get("firstName") or "").strip()
            last = (p.get("lastName") or "").strip()
            chinese = to_chinese_name(f"{last} {first}".strip())
            return chinese or f"{first} {last}".strip()

        if player:
            return one(player)
        if double:
            names = [
                one(double.get("leaguePlayerOne")),
                one(double.get("leaguePlayerTwo")),
            ]
            return " / ".join(n for n in names if n)
        return ""
