"""Official knockout draws, independent of the existing WTT match feed."""
from datetime import datetime, timedelta
import re
import time
import httpx
from data_sources.name_map import to_chinese_name
from data_sources.wtt import EVENTS_FALLBACK_URL, _is_main_event

API = "https://wtt-web-cms-api-prod.azurewebsites.net/api/cms/GetBrackets"
PROJECTS = {"男单": "MSINGLES", "女单": "WSINGLES", "男双": "MDOUBLES", "女双": "WDOUBLES", "混双": "XDOUBLES"}
ROUND_NAMES = {"FNL": "决赛", "SFNL": "半决赛", "QFNL": "四分之一决赛", "8FNL": "16 强", "R32": "32 强", "R64": "64 强", "R128": "128 强", "RND1": "资格赛第 1 轮", "RND2": "资格赛第 2 轮", "RND3": "资格赛第 3 轮", "RND4": "资格赛第 4 轮"}


def as_list(value):
    return value if isinstance(value, list) else [value] if isinstance(value, dict) else []


def parse_draws(data):
    if not data:
        return {}
    if not isinstance(data, dict) or not isinstance(data.get("Competition"), dict):
        raise ValueError("官方签表格式暂不支持")
    stages = {}
    for bracket in as_list(data["Competition"].get("Bracket")):
        stage = bracket.get("Code", "")
        rounds = []
        for group in as_list(bracket.get("BracketItems")):
            matches = []
            for row in as_list(group.get("BracketItem")):
                players = []
                for place in sorted(as_list(row.get("CompetitorPlace")), key=lambda p: int(p.get("Pos") or 0)):
                    competitor = place.get("Competitor") or {}
                    raw = str((competitor.get("Description") or {}).get("TeamName") or place.get("Code") or "TBD").strip()
                    name = "轮空" if place.get("Code") == "BYE" else "待定" if place.get("Code") == "TBD" else to_chinese_name(raw) or raw
                    result = place.get("Result")
                    previous = (place.get("PreviousUnit") or {}).get("Unit") or ""
                    athletes = ((competitor.get("Composition") or {}).get("Athlete") or [])
                    if isinstance(athletes, dict):
                        athletes = [athletes]
                    player_id = str(athletes[0].get("Code") or "") if len(athletes) == 1 else str(competitor.get("Code") or "") if not athletes and competitor.get("Type") == "A" else ""
                    players.append({"name": name, "raw": raw, "country": competitor.get("Organization") or "", "seed": competitor.get("Seed"), "score": str(result) if result not in (None, "") else "—", "winner": place.get("Wlt") == "W", "previous": previous.rstrip("-"), "code": place.get("Code", ""), "player_id": player_id if player_id.isdecimal() and int(player_id) > 0 else ""})
                if len(players) != 2:
                    continue
                bye = any(p["code"] == "BYE" for p in players)
                if bye:
                    for p in players:
                        p["score"] = "—"
                result = str(row.get("Result") or "")
                games = [(int(a), int(b)) for a,b in re.findall(r"(\d+)\s*:\s*(\d+)", result)]
                while games and games[-1] == (0,0):
                    games.pop()  # Provider pads completed matches with an unused 0:0 game.
                matches.append({"id": str(row.get("Code") or row.get("Unit") or "").rstrip("-"), "order": int(row.get("Order") or row.get("Position") or len(matches)+1), "players": players, "date": row.get("Date") or "", "time": row.get("Time") or "", "result": result, "sets": games, "bye": bye})
            if matches:
                matches.sort(key=lambda m: m["order"])
                code = str(group.get("Code") or "").rstrip("-")
                rounds.append({"code": code, "title": ROUND_NAMES.get(code, code), "matches": matches})
        # Order columns by actual predecessor relations. Counts only break ties.
        match_round = {m["id"]: i for i,r in enumerate(rounds) for m in r["matches"]}
        pending = set(range(len(rounds)))
        ordered = []
        while pending:
            ready = [i for i in pending if not any(match_round.get(p["previous"]) in pending and match_round.get(p["previous"]) != i for m in rounds[i]["matches"] for p in m["players"])]
            if not ready:
                raise ValueError("签表晋级关系存在循环")
            ready.sort(key=lambda i: (-len(rounds[i]["matches"]), rounds[i]["code"]))
            for i in ready:
                ordered.append(rounds[i])
                pending.remove(i)
        if ordered:
            stages[stage] = ordered
    return stages


def fetch_events():
    response = httpx.get(EVENTS_FALLBACK_URL, params={"q": int(time.time() // 300)}, timeout=20, follow_redirects=True)
    response.raise_for_status()
    now = datetime.now()
    rows = []
    for row in response.json():
        name = str(row.get("eventName") or "")
        if not _is_main_event(name):
            continue
        try:
            start = datetime.fromisoformat(row["startDateTime"]).replace(tzinfo=None)
            end = datetime.fromisoformat(row["endDateTime"]).replace(tzinfo=None)
            event_id = int(row["eventId"])
        except (ValueError, KeyError, TypeError):
            continue
        if end >= now - timedelta(days=90) and start <= now + timedelta(days=60):
            rows.append({"id": event_id, "name": name, "start": start.isoformat(), "end": end.isoformat()})
    rows.sort(key=lambda r: (not (r["start"][:10] <= now.date().isoformat() <= r["end"][:10]), abs((datetime.fromisoformat(r["start"]) - now).days)))
    return rows


def fetch_draws(event_id, project):
    if project not in PROJECTS.values():
        raise ValueError("不支持的项目")
    code = "TTE" + project + "-" * 31
    response = httpx.get(f"{API}/{int(event_id)}/{code}", params={"q": int(time.time() // 30)}, headers={"Cache-Control": "no-cache"}, timeout=20, follow_redirects=True)
    if response.status_code == 204:
        return {}
    response.raise_for_status()
    return parse_draws(response.json())
