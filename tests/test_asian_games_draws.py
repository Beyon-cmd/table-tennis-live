import unittest

from data_sources.asian_games_draws import parse_brackets


def _match(key, home, away, *, hwin=False, awin=False, detail="", bye=False):
    return {
        "Home": {"Name": home, "Org": "CHN" if home else "BYE", "Reg": home,
                 "Res": "4" if hwin and not bye else "", "Win": hwin},
        "Away": {"Name": away, "Org": "JPN" if away else "BYE", "Reg": away,
                 "Res": "4" if awin and not bye else "", "Win": awin},
        "Info": {"Key": key, "IsBye": bye, "DateTimeRaw": "2026-09-24T10:00:00+09:00",
                 "Extensions": [{"Code": "ResultDetailWinner", "Value": detail}]},
    }


class AsianGamesDrawTests(unittest.TestCase):
    def test_round_links_byes_and_away_winner_perspective(self):
        payload = [{"Code": "MAINDRAW", "Phases": [
            {"Code": "M.SINGLES-----------.SFNL", "Desc": "Semifinals", "Matches": [
                _match("semi1", "A", "B", awin=True, detail="11:7, 11:8, 7:11, 11:9, 11:6"),
                _match("semi2", "C", "", hwin=True, bye=True),
            ]},
            {"Code": "M.SINGLES-----------.FNL-", "Desc": "Final", "Matches": [
                _match("final", "B", "C"),
            ]},
        ]}]
        rounds = parse_brackets(payload, "M.SINGLES-----------")["MAIN"]
        self.assertEqual([r["title"] for r in rounds], ["半决赛", "决赛"])
        self.assertEqual(rounds[1]["matches"][0]["players"][0]["previous"], "semi1")
        self.assertEqual(rounds[1]["matches"][0]["players"][1]["previous"], "semi2")
        self.assertTrue(rounds[0]["matches"][1]["bye"])
        self.assertEqual(rounds[0]["matches"][0]["sets"][0], (7, 11))

    def test_unexpected_payload_rejected(self):
        with self.assertRaises(ValueError):
            parse_brackets({}, "M.SINGLES-----------")
