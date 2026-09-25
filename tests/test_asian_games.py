from __future__ import annotations

import json
import unittest
import zlib
from datetime import datetime

import httpx

from data_sources.asian_games import _official_json, apply_team_detail, parse_schedule
from models import STATUS_FINISHED, STATUS_LIVE, STATUS_UPCOMING


def _row(**changes):
    row = {
        "Key": "M.SINGLES-----------.R32-.000100--",
        "DateTimeRaw": "2026-09-24T10:00:00+09:00",
        "EventDesc": "Men's Singles",
        "PhaseDescA": "Round 2",
        "Status": "OFFICIAL",
        "IsLive": False,
        "Home": {"Name": "WANG Chuqin", "Org": "CHN", "Result": "3",
                 "Splits": [{"Res": "11"}, {"Res": "8"}, {"Res": "11"}, {"Res": "11"}]},
        "Away": {"Name": "HARIMOTO Tomokazu", "Org": "JPN", "Result": "1",
                 "Splits": [{"Res": "7"}, {"Res": "11"}, {"Res": "9"}, {"Res": "5"}]},
    }
    row.update(changes)
    return row


def test_official_wrapped_zlib():
    body = zlib.compress(json.dumps([_row()]).encode()).decode("latin-1").encode()
    response = httpx.Response(200, content=body, request=httpx.Request("GET", "https://example.com"))
    assert _official_json(response)[0]["Status"] == "OFFICIAL"


def test_finished_sets_and_names():
    match = parse_schedule(_row(), datetime(2026, 9, 24))
    assert match is not None
    assert match.status == STATUS_FINISHED
    assert (match.score_a, match.score_b) == (3, 1)
    assert match.sets == [(11, 7), (8, 11), (11, 9), (11, 5)]
    assert "亚运会" in match.competition


def test_live_current_game_and_unscored_upcoming():
    live = parse_schedule(_row(Status="RUNNING", IsLive=True,
        Home={"Name": "A", "Result": "1", "Splits": [{"Res": "11"}, {"Res": "6"}]},
        Away={"Name": "B", "Result": "0", "Splits": [{"Res": "8"}, {"Res": "4"}]}))
    assert live.status == STATUS_LIVE
    assert live.sets == [(11, 8)]
    assert live.current_set == (6, 4)
    upcoming = parse_schedule(_row(Status="SCHEDULED",
        Home={"Name": "A", "Result": "", "Splits": []},
        Away={"Name": "B", "Result": "", "Splits": []}))
    assert upcoming.status == STATUS_UPCOMING
    assert not upcoming.score_known


def test_completed_fourth_game_corrects_lagging_total_without_guessing_current_game():
    row = _row(
        Status="RUNNING", IsLive=True, EventDesc="Mixed Doubles",
        Home={"Name": "A", "Result": "2", "Splits": [
            {"Res": "11"}, {"Res": "10"}, {"Res": "11"}, {"Res": "5"}]},
        Away={"Name": "B", "Result": "1", "Splits": [
            {"Res": "7"}, {"Res": "12"}, {"Res": "7"}, {"Res": "11"}]},
    )
    match = parse_schedule(row)
    assert match is not None
    assert (match.score_a, match.score_b) == (2, 2)
    assert match.current_set is None
    assert match.score_reconciled

    # 10:9 尚未结束；不能为了对齐总比分把它算作一局。
    row["Home"]["Splits"][-1]["Res"] = "10"
    row["Away"]["Splits"][-1]["Res"] = "9"
    in_progress = parse_schedule(row)
    assert in_progress is not None
    assert (in_progress.score_a, in_progress.score_b) == (2, 1)
    assert in_progress.current_set == (10, 9)
    assert not in_progress.score_reconciled


def test_team_subunits():
    match = parse_schedule(_row(Type="T", EventDesc="Men's Team",
        Home={"Name": "People's Republic of China", "Org": "CHN", "Result": "1"},
        Away={"Name": "Japan", "Org": "JPN", "Result": "0"}))
    payload = {"Competitors": [{"Org": "CHN"}, {"Org": "JPN"}], "SubUnits": [{
        "Competitors": [
            {"Org": "CHN", "Name": "WANG Chuqin", "Result": "3"},
            {"Org": "JPN", "Name": "HARIMOTO Tomokazu", "Result": "1"},
        ],
        "Results": {"Periods": [{"ResHome": "11", "ResAway": "8"}]},
    }]}
    result = apply_team_detail(match, payload)
    assert result.player_a == "中国"
    assert result.games[0].score_a == 3
    assert result.games[0].sets == [(11, 8)]


class AsianGamesTests(unittest.TestCase):
    test_official_wrapped_zlib = staticmethod(test_official_wrapped_zlib)
    test_finished_sets_and_names = staticmethod(test_finished_sets_and_names)
    test_live_current_game_and_unscored_upcoming = staticmethod(test_live_current_game_and_unscored_upcoming)
    test_completed_fourth_game_corrects_lagging_total_without_guessing_current_game = staticmethod(
        test_completed_fourth_game_corrects_lagging_total_without_guessing_current_game)
    test_team_subunits = staticmethod(test_team_subunits)
