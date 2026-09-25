"""亚运会官方乒乓球签表，转为与 WTT 签表共用的画布模型。"""
from __future__ import annotations

import re

import httpx

from data_sources.asian_games import BASE, COUNTRIES, _official_json
from data_sources.name_map import to_chinese_name


PROJECTS = {
    "男单": "M.SINGLES-----------", "女单": "W.SINGLES-----------",
    "男双": "M.DOUBLES-----------", "女双": "W.DOUBLES-----------",
    "混双": "X.DOUBLES-----------", "男团": "M.TEAM--------------",
    "女团": "W.TEAM--------------",
}
ROUND_NAMES = {
    "R64-": "64 强", "R32-": "32 强", "8FNL": "16 强",
    "QFNL": "四分之一决赛", "SFNL": "半决赛", "FNL-": "决赛",
}


def _player(side: dict, previous: str = "", team: bool = False) -> dict:
    org = str(side.get("Org") or "")
    raw = str(side.get("Name") or "").strip()
    name = ("轮空" if org == "BYE" else "待定" if not raw
            else COUNTRIES.get(org, raw) if team
            else to_chinese_name(raw) or raw)
    return {
        "name": name, "raw": raw or name, "country": org,
        "seed": None, "score": str(side.get("Res") or "—"),
        "winner": bool(side.get("Win")), "previous": previous,
        "player_id": "", "reg": str(side.get("Reg") or ""),
    }


def parse_brackets(payload: object, project: str) -> dict:
    if not isinstance(payload, list):
        raise ValueError("亚运会官方签表格式异常")
    result = {}
    is_team = ".TEAM" in project
    for bracket in payload:
        if not isinstance(bracket, dict):
            continue
        rounds = []
        for phase in bracket.get("Phases") or []:
            code = str(phase.get("Code") or "")
            title = ROUND_NAMES.get(code.rsplit(".", 1)[-1], phase.get("Desc") or code)
            matches = []
            previous_round = rounds[-1]["matches"] if rounds else []
            rows = phase.get("Matches") or []
            can_link = len(previous_round) == len(rows) * 2
            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                info = row.get("Info") or {}
                home, away = row.get("Home") or {}, row.get("Away") or {}
                parent_ids = [previous_round[2 * index + pos]["id"] for pos in (0, 1)] if can_link else ["", ""]
                players = []
                for pos, side in enumerate((home, away)):
                    player = _player(side, parent_ids[pos], is_team)
                    # 已公布的下一轮选手与前轮胜者不符时不画误导性连线。
                    if can_link and player["reg"] and player["name"] not in ("轮空", "待定"):
                        previous_match = previous_round[2 * index + pos]
                        winners = [p["reg"] for p in previous_match["players"] if p["winner"]]
                        if winners and player["reg"] not in winners:
                            player["previous"] = ""
                    players.append(player)
                bye = bool(info.get("IsBye"))
                if bye:
                    for player in players:
                        player["score"] = "—"
                detail = next((str(e.get("Value") or "") for e in info.get("Extensions") or []
                               if e.get("Code") == "ResultDetailWinner"), "")
                sets = [tuple(map(int, pair)) for pair in re.findall(r"(\d+)\s*:\s*(\d+)", detail)]
                if away.get("Win") and not home.get("Win"):
                    sets = [(b, a) for a, b in sets]
                while sets and sets[-1] == (0, 0):
                    sets.pop()
                date_time = str(info.get("DateTimeRaw") or "")
                matches.append({
                    "id": str(info.get("Key") or ""), "order": index + 1,
                    "players": players, "date": date_time[:10],
                    "time": date_time[11:16] + " JST" if len(date_time) >= 16 else "",
                    "result": detail, "sets": sets, "bye": bye,
                })
            if matches:
                rounds.append({"code": code, "title": title, "matches": matches})
        if rounds:
            result["MAIN" if bracket.get("Code") == "MAINDRAW" else str(bracket.get("Code") or "其他")] = rounds
    return result


def fetch_brackets(project: str) -> dict:
    if project not in PROJECTS.values():
        raise ValueError("不支持的亚运会乒乓球项目")
    with httpx.Client(headers={"User-Agent": "Mozilla/5.0", "Referer": "https://results.asiangames2026.org/",
                               "Accept-Encoding": "identity", "Cache-Control": "no-cache"},
                      timeout=16.0, follow_redirects=True) as client:
        payload = _official_json(client.get(f"{BASE}/brackets/{project}"))
    return parse_brackets(payload, project)
