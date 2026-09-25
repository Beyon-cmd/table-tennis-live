"""WTT's public senior ranking feed; singles only, never infer missing ranks."""
import httpx

URL = "https://wtt-web-frontdoor-cthahjeqhbh6aqe3.a01.azurefd.net/ranking/SEN_SINGLES.json"


def parse_rankings(payload):
    result = {"MS": [], "WS": []}
    for row in payload.get("Result", []):
        event = row.get("SubEventCode")
        if event not in result:
            continue
        try:
            rank = int(row["CurrentRank"])
            points = int(row["RankingPointsYTD"])
        except (KeyError, ValueError, TypeError):
            continue
        if rank < 1 or not row.get("PlayerName"):
            continue
        result[event].append(dict(row, rank=rank, points=points))
    for rows in result.values():
        rows.sort(key=lambda r: (r["rank"], r["PlayerName"]))
    if not all(result.values()):
        raise ValueError("官方排名数据不完整")
    return result


def fetch_rankings():
    import time
    response = httpx.get(URL, params={"q": int(time.time())}, headers={"Cache-Control": "no-cache"}, timeout=20, follow_redirects=True)
    response.raise_for_status()
    return parse_rankings(response.json())
