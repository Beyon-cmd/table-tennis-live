"""日本 T.League 数据源（来源：tleague.jp 官网赛程页 + 比赛详情页）。

赛程页为服务端渲染的 HTML 表格，含比赛日期时间、男女组别、主客队与
已结束比赛的比分。已结束比赛的详情页（detail.php）含每场对阵的选手
与每局比分。官网没有公开的实时比分接口，因此不提供 LIVE 比分。
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from data_sources.base import DataSource, make_client
from data_sources.name_map import to_chinese_name, to_chinese_team
from models import Game, Match, STATUS_FINISHED, STATUS_UPCOMING

PAGE_URL = "https://tleague.jp/schedule/"
DETAIL_URL = "https://tleague.jp/schedule/detail.php?id={match_id}"


class TLeagueDataSource(DataSource):
    name = "T.League"

    def __init__(self):
        self._client = make_client()
        self._rows_cache: tuple[list[dict] | None, float] = (None, 0.0)
        self._detail_cache: dict[str, tuple[list[Game] | None, float]] = {}

    def get_matches(self) -> list[Match]:
        rows = self._fetch_rows()
        now = datetime.now()
        matches: list[Match] = []
        finished: list[Match] = []
        for row in rows:
            match = self._build_match(row, now)
            if match is not None:
                matches.append(match)
                if match.status == STATUS_FINISHED and row.get("id"):
                    finished.append(match)
        # 预热最近 6 场的选手对阵与每局比分（缓存 1 小时），
        # 既方便搜索选手名，也避免详情页等待；其余比赛打开详情时按需抓取
        finished.sort(key=lambda m: m.start_time, reverse=True)
        for match in finished[:6]:
            match.games = self._get_detail(match.id.removeprefix("tleague:"))
        return matches

    def get_live_matches(self) -> list[Match]:
        return []

    def get_schedule(self) -> list[Match]:
        return self.get_matches()

    def get_match_detail(self, match_id: str) -> Match | None:
        row_id = match_id.removeprefix("tleague:")
        for row in self._fetch_rows():
            if row.get("id") and str(row["id"]) == row_id:
                match = self._build_match(row, datetime.now())
                if match is not None:
                    match.games = self._get_detail(row_id)
                    return match
        return None

    # ---------------- 数据抓取 ----------------
    def _fetch_rows(self) -> list[dict]:
        cached, ts = self._rows_cache
        now_ts = datetime.now().timestamp()
        if cached is not None and now_ts - ts < 10:
            return cached
        response = self._client.get(PAGE_URL)
        response.raise_for_status()
        rows = self._parse_html(response.text)
        self._rows_cache = (rows, now_ts)
        return rows

    def _get_detail(self, match_id: str) -> list[Game]:
        """比赛详情页里的单场对阵与每局比分（缓存 1 小时）。"""
        item = self._detail_cache.get(match_id)
        now_ts = datetime.now().timestamp()
        if item is not None and now_ts - item[1] < 3600:
            return item[0] or []
        games: list[Game] = []
        try:
            response = self._client.get(DETAIL_URL.format(match_id=match_id))
            response.raise_for_status()
            games = self._parse_detail(response.text)
        except Exception:
            games = []
        self._detail_cache[match_id] = (games, now_ts)
        return games

    @staticmethod
    def _parse_html(html: str) -> list[dict]:
        rows: list[dict] = []
        for raw in re.split(r"<tr\b", html):
            row = raw[: raw.find("</tr>")] if "</tr>" in raw else raw
            date_m = re.search(
                r"(\d{4})年\s*(\d{1,2})月(\d{1,2})日\([^)]*\)\s*(\d{1,2}):(\d{2})",
                row,
            )
            if not date_m:
                continue
            year, month, day, hour, minute = (int(x) for x in date_m.groups())
            try:
                start = datetime(year, month, day, hour, minute)
            except ValueError:
                continue
            gender_m = re.search(r">(男子|女子)<", row)
            gender = gender_m.group(1) if gender_m else ""
            teams = re.findall(r'<span class="d-none d-lg-inline">([^<]+)</span>', row)
            if len(teams) < 2:
                continue
            # 官网曾把 <b> 改为带 class 的标签，并会使用全角连字符；不要
            # 因展示样式调整而漏掉团体大比分。
            score_m = re.search(
                r"<b[^>]*>\s*<span[^>]*>(\d+)</span>\s*[-－]\s*"
                r"<span[^>]*>(\d+)</span>\s*</b>",
                row,
                re.S,
            )
            detail_m = re.search(r"detail\.php\?id=(\d+)", row)
            rows.append(
                {
                    "id": detail_m.group(1) if detail_m else None,
                    "start": start,
                    "gender": gender,
                    "home": teams[0].strip(),
                    "away": teams[1].strip(),
                    "score": tuple(int(x) for x in score_m.groups()) if score_m else None,
                }
            )
        return rows

    @staticmethod
    def _parse_detail(html: str) -> list[Game]:
        """从详情页解析每场对阵：选手名 + 每局比分。"""
        games: list[Game] = []
        # 按 “第Nマッチ” 分块，块结束于下一个 h2 标题
        parts = re.split(r"第\d+マッチ", html)
        for part in parts[1:]:
            block = part.split("<h2", 1)[0]
            py_blocks = re.findall(
                r'<div class="text-center py-4">(.*?)</div>', block, re.S
            )
            if len(py_blocks) < 2:
                continue

            def players(text: str) -> str:
                names = re.findall(
                    r'/player/detail\.php\?player=\d+[^>]*>([^<]+)</a>', text
                )
                return " / ".join(
                    to_chinese_name(n.strip()) or n.strip() for n in names
                )

            home = players(py_blocks[0])
            away = players(py_blocks[1])
            if not home or not away:
                continue
            sets = [
                (int(a), int(b))
                for a, b in re.findall(
                    r'<div class="text-center">\s*(\d+)\s*-\s*(\d+)\s*</div>', block
                )
            ]
            if not sets:
                continue
            score_a = sum(1 for a, b in sets if a > b)
            score_b = sum(1 for a, b in sets if b > a)
            games.append(
                Game(
                    player_a=home,
                    player_b=away,
                    score_a=score_a,
                    score_b=score_b,
                    sets=sets,
                )
            )
        return games

    # ---------------- 解析 ----------------
    def _build_match(self, row: dict, now: datetime) -> Match | None:
        start = row["start"]
        finished = row["score"] is not None
        if not finished and start > now + timedelta(days=7):
            return None  # 未开始的只保留未来 7 天
        gender = f" · {row['gender']}" if row["gender"] else ""
        competition = f"日本 T.League{gender}"
        home_raw = row["home"]
        away_raw = row["away"]
        home_name = to_chinese_team(home_raw) or home_raw
        away_name = to_chinese_team(away_raw) or away_raw

        return Match(
            id=f"tleague:{row['id'] or start.strftime('%Y%m%d%H%M')}",
            source="T.League",
            competition=competition,
            status=STATUS_FINISHED if finished else STATUS_UPCOMING,
            start_time=start,
            player_a=home_name,
            player_b=away_name,
            player_a_raw="" if home_name == home_raw else home_raw,
            player_b_raw="" if away_name == away_raw else away_raw,
            score_a=row["score"][0] if finished else 0,
            score_b=row["score"][1] if finished else 0,
            score_known=finished,
            games=[],
            last_update=now,
        )
