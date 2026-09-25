"""WTT 数据源（来源：世界乒乓球官网 worldtabletennis.com 的公开数据）。

使用官网页面自身加载的公开静态文件（Azure Front Door），不需要登录/付费 API：
- 当前进行中的赛事: websitestaticapifiles/general/wtt_live_results_event_id.json
- 赛事赛程:          websitecacheddata/{eventId}/schedule/schedule.json
- 官方结果清单:      websitecacheddata/{eventId}/officialresult/officialresult_minimal.json
- 最近官方结果卡:    websitestaticapifiles/{eventId}/{eventId}_take_10_official_results.json
- 进行中的比赛列表:  websitestaticapifiles/running-events/{eventId}/{eventId}_livematchids.json
- 实时比赛卡:        matchdata/{eventId}/{matchId}.json

使用官方结果索引逐场补齐完整比赛卡，包含选手、每局比分、总比分。

赛事等级过滤：只展示 WTT 常规挑战赛（Contender）及以上等级的赛事
（大满贯 Smash、总决赛 Finals、冠军赛 Champions、球星挑战赛 Star Contender、
常规挑战赛 Contender），支线赛（Feeder）、青少年赛（Youth）、
ITTF 赛事等一律不显示。
"""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

from data_sources.base import DataSource, make_client
from data_sources.name_map import to_chinese_name
from data_sources.wtt_time import offset_for_event, venue_to_local
from models import Match, STATUS_FINISHED, STATUS_LIVE, STATUS_UPCOMING

FRONT = "https://wtt-web-frontdoor-cthahjeqhbh6aqe3.a01.azurefd.net"
LIVE_API = "https://wtt-web-frontdoor-withoutcache-cqakg0andqf5hchn.a01.azurefd.net"

EVENTS_URL = f"{FRONT}/websitestaticapifiles/general/wtt_live_results_event_id.json"
EVENTS_FALLBACK_URL = (
    f"{FRONT}/websitestaticapifiles/general/wtt_upcoming_only_events_list.json"
)

# WTT 主等级赛事名称关键词（小写匹配）
_MAIN_EVENT_KEYWORDS = (
    "wtt champions",       # 冠军赛
    "wtt star contender",  # 球星挑战赛
    "wtt contender",       # 常规挑战赛
)


def _norm(code: str) -> str:
    """赛程单元 Code 与官方结果 documentCode 的末尾横线数量不同，去掉横线统一比较。"""
    return code.rstrip("-")


def _is_main_event(name: str) -> bool:
    """是否 WTT 常规挑战赛（Contender）及以上等级的赛事。"""
    low = (name or "").lower()
    if "youth smash" in low:
        return False
    if "smash" in low:
        return True  # 大满贯：China Smash / Singapore Smash / US Smash 等
    if low.startswith("wtt ") and "finals" in low:
        return True  # WTT 总决赛 / WTT Cup Finals
    return any(k in low for k in _MAIN_EVENT_KEYWORDS)


class WTTDataSource(DataSource):
    name = "WTT"

    def __init__(self):
        self._client = make_client()
        self._cache: dict[str, tuple[object, float]] = {}
        self._event_match_cache: dict[int, list[Match]] = {}
        self._event_offsets: dict[int, timedelta] = {}

    def _cached(self, key: str, ttl: float):
        item = self._cache.get(key)
        if item is None:
            return None
        value, ts = item
        return value if datetime.now().timestamp() - ts < ttl else None

    def _store(self, key: str, value) -> None:
        self._cache[key] = (value, datetime.now().timestamp())

    def _get_json(self, url: str, key: str, ttl: float):
        cached = self._cached(key, ttl)
        if cached is not None:
            return cached
        # CDN 曾返回前一天的直播/赛程文件。动态请求使用时间桶查询参数，
        # 配合 no-cache 重新验证；历史完赛卡仍使用长期缓存。
        bucket = int(datetime.now().timestamp() // max(2, min(ttl, 120)))
        response = self._client.get(url, params={"_refresh": bucket},
                                    headers={"Cache-Control": "no-cache"})
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type:
            raise ValueError(f"非 JSON 响应: {content_type}")
        data = response.json()
        self._store(key, data)
        return data

    # ---------------- 对外接口 ----------------
    def get_matches(self) -> list[Match]:
        events = self._get_events()
        matches: list[Match] = []
        failures = 0
        for event_id, event_name in events:
            try:
                rows = self._event_matches(event_id, event_name)
                self._event_match_cache[event_id] = rows
                matches.extend(rows)
            except Exception:
                failures += 1
                matches.extend(replace(row, data_stale=True)
                               for row in self._event_match_cache.get(event_id, []))
        if events and failures == len(events) and not matches:
            raise RuntimeError("所有 WTT 赛事取数失败")
        return matches

    def get_live_matches(self) -> list[Match]:
        return [m for m in self.get_matches() if m.status == STATUS_LIVE]

    def get_schedule(self) -> list[Match]:
        return [m for m in self.get_matches() if m.status != STATUS_LIVE]

    def get_match_detail(self, match_id: str) -> Match | None:
        if not match_id.startswith("wtt:"):
            return None
        for m in self.get_matches():
            if m.id == match_id:
                return m
        return None

    # ---------------- 数据抓取 ----------------
    def _get_events(self) -> list[tuple[int, str]]:
        primary_failed = False
        try:
            data = self._get_json(EVENTS_URL, "events", ttl=120)
            if isinstance(data, list) and data:
                return [
                    (int(e["eventId"]), str(e["eventName"]))
                    for e in data
                    if _is_main_event(str(e.get("eventName") or ""))
                ]
        except Exception:
            primary_failed = True
        try:
            data = self._get_json(EVENTS_FALLBACK_URL, "events_fallback", ttl=600)
            now = datetime.now()
            picked: list[tuple[int, str]] = []
            for e in data or []:
                event_name = str(e.get("eventName") or "")
                if not _is_main_event(event_name):
                    continue
                try:
                    start = datetime.fromisoformat(e.get("startDateTime") or "")
                    end = datetime.fromisoformat(e.get("endDateTime") or "")
                except ValueError:
                    continue
                if start <= now + timedelta(days=1) and end >= now - timedelta(days=1):
                    picked.append((int(e["eventId"]), event_name))
            if primary_failed and not picked and self._event_match_cache:
                raise RuntimeError("WTT 实时赛事列表暂不可用")
            return picked[:3]
        except Exception as exc:
            raise RuntimeError("WTT 赛事列表取数失败") from exc

    def _event_matches(self, event_id: int, event_name: str) -> list[Match]:
        now = datetime.now()
        event_offset = self._event_offset(event_id)
        if event_offset is None:
            raise ValueError(f"WTT 赛事 {event_id} 的场馆时区未核实")
        units = self._get_schedule(event_id)
        # 新版 livematchids 返回 {d: documentCode, ...} 对象，赛程 Code 的
        # 尾部横线数量又不同；用归一化 Code 作索引，保留完整 Code 请求比赛卡。
        live_codes = self._get_live_ids(event_id)
        live_ids = set(live_codes)
        with ThreadPoolExecutor(max_workers=4) as pool:
            cards = pool.map(lambda code: self._get_match_data(event_id, code), live_codes.values())
            live_data = dict(zip(live_codes, cards))
        results = self._get_results(event_id)  # 最近官方结果（含比赛卡）
        result_min = self._get_result_minimal(event_id)  # 全部官方结果（时间/代码）
        # 最近十场不是完整结果库。使用清单中的完整 documentCode 获取历史卡，
        # 已结束的有效卡缓存一天，避免每轮刷新重复下载。
        missing = [(key, row) for key, row in result_min.items() if key not in results]
        def load_result(item):
            key, row = item
            card = self._get_match_data(event_id, row["documentCode"], finished=True)
            return key, card
        with ThreadPoolExecutor(max_workers=8) as pool:
            for key, card in pool.map(load_result, missing):
                if self._parse_match_data(card) is not None:
                    results[key] = {"match_card": card}

        matches: list[Match] = []
        seen: set[str] = set()
        # 直播卡独立于赛程发布，不能要求先存在赛程条目才展示。
        for key, card in live_data.items():
            if not card:
                continue
            match = self._build_from_card(event_name, key, {"match_card": card}, None, now,
                                          event_offset)
            if match is None:
                continue
            parsed = self._parse_match_data(card)
            match.score_known = parsed is not None
            utc_start = card.get("matchStartTimeUTC")
            if utc_start:
                try:
                    match.start_time = datetime.fromisoformat(utc_start.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
                except ValueError:
                    pass
            if str(card.get("resultStatus", "")).upper() not in {"OFFICIAL", "FINISHED", "FINAL"}:
                match.status = STATUS_LIVE
                if parsed is not None:
                    match.score_a, match.score_b, points = parsed
                    played = match.score_a + match.score_b
                    match.sets = points[:played]
                    match.current_set = points[played] if len(points) > played else None
            match.id = f"wtt:{event_id}:{key}"
            matches.append(match)
            seen.add(key)
        for unit in units:
            code = unit.get("Code") or ""
            if not code:
                continue
            key = _norm(code)
            if key in seen:
                continue
            seen.add(key)
            match = self._build_match(
                event_name,
                unit,
                live_ids,
                live_data,
                results.get(key),
                result_min.get(key),
                now,
                event_offset,
            )
            if match is not None:
                match.id = f"wtt:{event_id}:{key}"
                matches.append(match)

        # 结果卡里有但赛程单元缺失的比赛（直接用比赛卡数据）
        for key, card in results.items():
            if key in seen:
                continue
            match = self._build_from_card(event_name, key, card, result_min.get(key), now,
                                          event_offset)
            if match is not None:
                match.id = f"wtt:{event_id}:{key}"
                matches.append(match)
        return matches

    def _event_offset(self, event_id: int) -> timedelta | None:
        if event_id in self._event_offsets:
            return self._event_offsets[event_id]
        data = self._get_json(EVENTS_FALLBACK_URL, "events_fallback", ttl=600)
        for row in data if isinstance(data, list) else []:
            try:
                if int(row.get("eventId")) != event_id:
                    continue
            except (TypeError, ValueError):
                continue
            offset = offset_for_event(row)
            if offset is not None:
                self._event_offsets[event_id] = offset
            return offset
        return None

    def _get_schedule(self, event_id: int) -> list[dict]:
        url = f"{FRONT}/websitecacheddata/{event_id}/schedule/schedule.json"
        data = self._get_json(url, f"sched-{event_id}", ttl=60)
        units: list[dict] = []
        for comp in data or []:
            units.extend((comp.get("Competition") or {}).get("Unit") or [])
        return units

    def _get_live_ids(self, event_id: int) -> dict[str, str]:
        # 不缓存域名现会重定向到网页；列表仍由 frontdoor 静态域名提供。
        url = f"{FRONT}/websitestaticapifiles/running-events/{event_id}/{event_id}_livematchids.json"
        try:
            data = self._get_json(url, f"live-{event_id}", ttl=1)
            if not isinstance(data, list):
                return {}
            codes: dict[str, str] = {}
            for item in data:
                # 新格式：{"e": "3254", "d": "...document code..."}；
                # 兼容旧格式：直接给 document code 字符串。
                code = item.get("d") if isinstance(item, dict) else item
                if code:
                    code = str(code)
                    codes[_norm(code)] = code
            return codes
        except Exception:
            return {}

    def _get_match_data(self, event_id: int, match_id: str, finished: bool = False) -> dict | None:
        # 旧 /matchdata 已重定向到网站 HTML；实时 JSON 迁至 matchcentre。
        url = f"{FRONT}/matchdata/matchcentre/{event_id}/{match_id}.json"
        try:
            data = self._get_json(url, f"match-{event_id}-{match_id}", ttl=86400 if finished else 1)
            if finished and self._parse_match_data(data) is None:
                self._cache.pop(f"match-{event_id}-{match_id}", None)
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _get_result_minimal(self, event_id: int) -> dict[str, dict]:
        """全部官方结果清单：{归一化代码: {startDateLocal, subEventType}}"""
        url = f"{FRONT}/websitecacheddata/{event_id}/officialresult/officialresult_minimal.json"
        try:
            data = self._get_json(url, f"result-min-{event_id}", ttl=120)
        except Exception:
            return {}
        out: dict[str, dict] = {}
        for row in data or []:
            code = _norm(str(row.get("documentCode") or ""))
            if code:
                out[code] = row
        return out

    def _get_results(self, event_id: int) -> dict[str, dict]:
        """最近官方结果（含完整比赛卡）：{归一化代码: 结果对象}"""
        url = (
            f"{FRONT}/websitestaticapifiles/{event_id}/"
            f"{event_id}_take_10_official_results.json"
        )
        try:
            data = self._get_json(url, f"results-{event_id}", ttl=120)
        except Exception:
            return {}
        out: dict[str, dict] = {}
        for row in data or []:
            code = _norm(str((row.get("match_card") or {}).get("documentCode") or row.get("documentCode") or ""))
            if code:
                out[code] = row
        return out

    # ---------------- 解析 ----------------
    def _build_match(
        self,
        event_name: str,
        unit: dict,
        live_ids: set[str],
        live_data: dict[str, dict | None],
        result: dict | None,
        result_min: dict | None,
        now: datetime,
        event_offset: timedelta | None = None,
    ) -> Match | None:
        code = unit.get("Code") or ""
        start_text = unit.get("StartDate")
        if not code or not start_text:
            return None
        key = _norm(code)
        try:
            start = datetime.fromisoformat(start_text)
        except ValueError:
            return None
        if event_offset is not None:
            start = venue_to_local(start, event_offset)

        starts = (unit.get("StartList") or {}).get("Start") or []
        if len(starts) < 2:
            return None
        names = []
        raws = []
        player_ids = []
        for s in starts[:2]:
            competitor = s.get("Competitor") or {}
            desc = competitor.get("Description") or {}
            raw = desc.get("TeamName") or competitor.get("Code") or "TBD"
            display, raw_name = self._localize(raw)
            org = competitor.get("Organization") or ""
            names.append(f"{display} ({org})" if org else display)
            raws.append(raw_name)
            player_ids.append(self._competitor_player_id(competitor))
        if any(n in ("TBD", "TBD ", "—", "") for n in names):
            return None

        status_raw = unit.get("ScheduleStatus") or ""
        sub_event = unit.get("SubEvent") or ""
        competition = f"{event_name} · {sub_event}" if sub_event else event_name

        score_a = score_b = 0
        sets: list[tuple[int, int]] = []
        score_known = False
        current_set = None

        if key in live_ids or status_raw == "Official":
            parsed = self._parse_match_data(live_data.get(key))
            if parsed is not None:
                score_a, score_b, sets = parsed
                score_known = True
                if key in live_ids and len(sets) > score_a + score_b:
                    current_set = sets[score_a + score_b]
                    sets = sets[:score_a + score_b]
            elif key in live_ids:
                score_known = False

        if result is not None:
            card = result.get("match_card") or {}
            names, raws, score_a, score_b, sets = self._card_data(card, names, raws)
            player_ids = self._card_player_ids(card) or player_ids
            status = STATUS_FINISHED
            start = self._result_start(result_min, start, event_offset)
            score_known = self._parse_match_data(card) is not None
            current_set = None
        elif key in live_ids:
            status = STATUS_LIVE
        elif status_raw == "Official":
            status = STATUS_FINISHED
        else:
            status = STATUS_UPCOMING

        if status == STATUS_UPCOMING and not (
            now - timedelta(hours=12) <= start <= now + timedelta(hours=24)
        ):
            return None
        return Match(
            id=f"wtt:{code}",
            source="WTT",
            competition=competition,
            status=status,
            start_time=start,
            player_a=names[0],
            player_b=names[1],
            player_a_raw=raws[0],
            player_b_raw=raws[1],
            score_a=score_a,
            score_b=score_b,
            sets=sets,
            current_set=current_set,
            score_known=score_known,
            last_update=now,
            player_a_id=player_ids[0],
            player_b_id=player_ids[1],
        )

    def _build_from_card(
        self,
        event_name: str,
        key: str,
        result: dict,
        result_min: dict | None,
        now: datetime,
        event_offset: timedelta | None = None,
    ) -> Match | None:
        card = result.get("match_card") or {}
        names, raws, score_a, score_b, sets = self._card_data(card, [None, None], ["", ""])
        player_ids = self._card_player_ids(card) or ["", ""]
        if not names[0] or not names[1]:
            return None
        sub = card.get("subEventName") or result.get("subEventType") or ""
        competition = f"{event_name} · {sub}" if sub else event_name
        start = now
        if result_min and result_min.get("startDateLocal"):
            try:
                start = datetime.fromisoformat(result_min["startDateLocal"])
                if event_offset is not None:
                    start = venue_to_local(start, event_offset)
            except ValueError:
                pass
        return Match(
            id=f"wtt:{key}",
            source="WTT",
            competition=competition,
            status=STATUS_FINISHED,
            start_time=start,
            player_a=names[0],
            player_b=names[1],
            player_a_raw=raws[0],
            player_b_raw=raws[1],
            score_a=score_a,
            score_b=score_b,
            sets=sets,
            score_known=True,
            last_update=now,
            player_a_id=player_ids[0],
            player_b_id=player_ids[1],
        )

    @staticmethod
    def _competitor_player_id(competitor: dict) -> str:
        athletes = ((competitor.get("Composition") or {}).get("Athlete") or [])
        if isinstance(athletes, dict):
            athletes = [athletes]
        if len(athletes) == 1:
            code = str(athletes[0].get("Code") or (athletes[0].get("Description") or {}).get("IfId") or "")
            return code if code.isdecimal() and int(code) > 0 else ""
        if not athletes and competitor.get("Type") == "A":
            code = str(competitor.get("Code") or "")
            return code if code.isdecimal() and int(code) > 0 else ""
        return ""

    @staticmethod
    def _card_player_ids(card: dict) -> list[str]:
        competitors = card.get("competitiors") or []
        if len(competitors) < 2:
            return []
        ids = []
        for competitor in competitors[:2]:
            players = competitor.get("players") or []
            if len(players) != 1:
                ids.append("")
                continue
            code = str(players[0].get("playerId") or "")
            ids.append(code if code.isdecimal() and int(code) > 0 else "")
        return ids

    @staticmethod
    def _card_data(
        card: dict,
        fallback_names: list[str | None],
        fallback_raws: list[str],
    ):
        """从官方结果比赛卡提取 (选手, 原文, score_a, score_b, sets)。"""
        names = list(fallback_names)
        raws = list(fallback_raws)
        competitors = card.get("competitiors") or []
        if len(competitors) >= 2:
            names = []
            raws = []
            for c in competitors[:2]:
                raw = c.get("competitiorName") or "?"
                display, raw_name = WTTDataSource._localize(raw)
                org = c.get("competitiorOrg") or ""
                names.append(f"{display} ({org})" if org else display)
                raws.append(raw_name)
        overall = (
            card.get("overallScores")
            or card.get("resultOverallScores")
            or card.get("OverallScores")
        )
        score_a = score_b = 0
        if overall:
            digits = re.findall(r"\d+", str(overall))
            if len(digits) >= 2:
                score_a, score_b = int(digits[0]), int(digits[1])
        games = (
            card.get("resultsGameScores")
            or card.get("gameScores")
            or card.get("GameScores")
        )
        sets: list[tuple[int, int]] = []
        if isinstance(games, list):
            for g in games:
                pair = WTTDataSource._parse_game_pair(g)
                if pair:
                    sets.append(pair)
        elif isinstance(games, str):
            for token in games.split(","):
                pair = WTTDataSource._parse_game_pair(token.strip())
                if pair:
                    sets.append(pair)
        # 官方数据会把未打的局补成 0:0，按已结束局数裁掉
        played = score_a + score_b
        if played > 0 and len(sets) > played:
            sets = sets[:played]
        return names, raws, score_a, score_b, sets

    @staticmethod
    def _localize(raw: str) -> tuple[str, str]:
        """官方英文名 -> (中文展示名, 原文名)；未收录则展示原名。"""
        chinese = to_chinese_name(raw)
        if chinese:
            return chinese, raw
        return raw, ""

    @staticmethod
    def _result_start(result_min: dict | None, fallback: datetime,
                      event_offset: timedelta | None = None) -> datetime:
        if result_min and result_min.get("startDateLocal"):
            try:
                start = datetime.fromisoformat(result_min["startDateLocal"])
                return venue_to_local(start, event_offset) if event_offset is not None else start
            except ValueError:
                pass
        return fallback

    @staticmethod
    def _parse_match_data(data: dict | None):
        if not data:
            return None
        try:
            card = data.get("matchCardResult") or data
            # 当前 matchcentre 接口直接返回比赛卡；旧接口把它包在
            # match_result 中。两种格式都从实际含比分的对象解析。
            mresult = card.get("match_result") or card
            overall = (
                mresult.get("OverallScores")
                or mresult.get("overallScores")
                or mresult.get("resultOverallScores")
            )
            games = (
                mresult.get("GameScores")
                or mresult.get("gameScores")
                or mresult.get("ResultsGameScores")
                or mresult.get("resultsGameScores")
            )
            score_a = score_b = 0
            if overall is not None:
                pair = WTTDataSource._parse_game_pair(overall)
                if pair is None:
                    return None
                score_a, score_b = pair
            sets: list[tuple[int, int]] = []
            if isinstance(games, list):
                for g in games:
                    pair = WTTDataSource._parse_game_pair(g)
                    if pair:
                        sets.append(pair)
            elif isinstance(games, str):
                for token in games.split(","):
                    pair = WTTDataSource._parse_game_pair(token.strip())
                    if pair:
                        sets.append(pair)
            # 未打的局以 0-0 占位，不要作为小局比分显示。
            sets = [pair for pair in sets if pair != (0, 0)]
            if overall is None and not sets:
                return None
            return score_a, score_b, sets
        except Exception:
            return None

    @staticmethod
    def _parse_game_pair(value) -> tuple[int, int] | None:
        if isinstance(value, dict):
            a, b = value.get("HomePeriodScore"), value.get("AwayPeriodScore")
            if a is not None and b is not None:
                return int(a), int(b)
        if not isinstance(value, str):
            value = str(value or "")
        m = re.search(r"(\d+)\s*[-:]\s*(\d+)", value)
        if not m:
            return None
        return int(m.group(1)), int(m.group(2))
