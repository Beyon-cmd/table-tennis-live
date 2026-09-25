import unittest
from datetime import datetime
from unittest.mock import Mock
from models import Match

from data_sources.wtt import WTTDataSource, _norm
from data_sources.majors import MajorsDataSource
from data_sources.major_team_results import TEAM_RESULTS


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.source = WTTDataSource()

    def tearDown(self):
        self.source._client.close()

    def test_wtt_partial_outage_keeps_only_failed_event_stale(self):
        a = Match("wtt:a", "WTT", "A", "live", datetime.now(), "A", "B", score_a=1)
        b = Match("wtt:b", "WTT", "B", "live", datetime.now(), "C", "D", score_a=2)
        self.source._get_events = Mock(return_value=[(1, "A"), (2, "B")])
        self.source._event_matches = Mock(side_effect=[[a], [b], RuntimeError("offline"), [b]])
        self.source.get_matches()
        rows = self.source.get_matches()
        self.assertEqual([(row.id, row.data_stale) for row in rows],
                         [("wtt:a", True), ("wtt:b", False)])

    def test_wtt_event_list_failure_does_not_erase_cached_matches(self):
        cached = Match("wtt:a", "WTT", "A", "live", datetime.now(), "A", "B")
        self.source._event_match_cache[1] = [cached]
        self.source._get_json = Mock(side_effect=[RuntimeError("offline"), []])
        with self.assertRaises(RuntimeError):
            self.source._get_events()

    def unit(self, code="TEST--", status="Official"):
        return {"Code": code, "StartDate": datetime.now().isoformat(), "ScheduleStatus": status,
                "StartList": {"Start": [{"Competitor": {"Description": {"TeamName": n}}}
                                        for n in ("Player A", "Player B")]}}

    def test_history_beyond_recent_ten_and_event_ids(self):
        s = self.source
        s._get_schedule = Mock(return_value=[self.unit(f"CODE{i}--") for i in range(12)])
        s._get_live_ids = Mock(return_value={})
        s._get_results = Mock(return_value={})
        s._get_result_minimal = Mock(return_value={f"CODE{i}": {"documentCode": f"CODE{i}----------"} for i in range(12)})
        s._get_match_data = Mock(return_value={"overallScores": "3-1", "gameScores": "11-8,7-11,11-5,11-4,0-0"})
        matches = s._event_matches(3254, "Test")
        self.assertEqual(len(matches), 12)
        self.assertTrue(all(m.has_score and len(m.sets) == 4 for m in matches))
        self.assertTrue(all(m.id.startswith("wtt:3254:") for m in matches))
        self.assertEqual(s._get_match_data.call_count, 12)

    def test_live_current_game_separated(self):
        s = self.source
        card = {"overallScores": "1-1", "gameScores": "11-7,8-11,6-4,0-0,0-0"}
        m = s._build_match("Test", self.unit(status="Running"), {"TEST"}, {"TEST": card}, None, None, datetime.now())
        self.assertEqual(m.sets, [(11,7),(8,11)])
        self.assertEqual(m.current_set, (6,4))
        self.assertEqual((m.score_a,m.score_b), (1,1))

    def test_live_card_without_schedule(self):
        s = self.source
        s._get_schedule = Mock(return_value=[])
        s._get_live_ids = Mock(return_value={"LIVE": "LIVE--"})
        s._get_results = Mock(return_value={})
        s._get_result_minimal = Mock(return_value={})
        s._get_match_data = Mock(return_value={
            "competitiors": [{"competitiorName": "Player A"}, {"competitiorName": "Player B"}],
            "overallScores": "1-1", "gameScores": "11-7,8-11,6-4,0-0",
            "resultStatus": "LIVE", "matchStartTimeUTC": "2026-09-19T01:00:00Z"})
        matches = s._event_matches(3254, "Test")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].status, "live")
        self.assertEqual(matches[0].current_set, (6,4))
        self.assertEqual(matches[0].sets, [(11,7),(8,11)])

    def test_unknown_is_not_zero(self):
        m = self.source._build_match("Test", self.unit(), set(), {}, None, None, datetime.now())
        self.assertFalse(m.score_known)
        self.assertFalse(m.has_score)
        self.assertIsNone(self.source._parse_match_data({"error": "not available"}))
        self.assertEqual(self.source._parse_match_data({"overallScores": "0 - 0"}), (0,0,[]))

    def test_dynamic_request_revalidates_cdn_and_caches_locally(self):
        response = Mock()
        response.headers = {"content-type": "application/json"}
        response.json.return_value = []
        self.source._client.get = Mock(return_value=response)
        self.source._get_json("https://example.test/live.json", "test", 1)
        self.source._get_json("https://example.test/live.json", "test", 1)
        self.assertEqual(self.source._client.get.call_count, 1)
        kwargs = self.source._client.get.call_args.kwargs
        self.assertIn("_refresh", kwargs["params"])
        self.assertEqual(kwargs["headers"]["Cache-Control"], "no-cache")

    def test_team_totals_and_games(self):
        matches = {m.id: m for m in MajorsDataSource().get_historical_matches()}
        self.assertEqual(len(TEAM_RESULTS), 39)
        self.assertTrue(all(m.games for m in matches.values() if m.id.startswith("major:") and "团体" in m.competition))
        for (event, cat), (day, url, rows) in TEAM_RESULTS.items():
            with self.subTest(event=event, category=cat):
                m = matches[f"major:{event}:{cat}"]
                self.assertTrue(m.games)
                self.assertTrue(url.startswith("https://"))
                self.assertEqual(m.start_time.date().isoformat(), day)
                if cat == "混合团体":
                    total = (sum(g.score_a for g in m.games), sum(g.score_b for g in m.games))
                else:
                    total = (sum(g.score_a > g.score_b for g in m.games), sum(g.score_a < g.score_b for g in m.games))
                self.assertEqual(total, (m.score_a,m.score_b))
                for g in m.games:
                    if g.sets:
                        self.assertEqual(len(g.sets), g.score_a + g.score_b)
                        self.assertEqual(sum(a>b for a,b in g.sets), g.score_a)
                        self.assertTrue(all(max(a,b) >= 11 and abs(a-b)>=2 for a,b in g.sets))


if __name__ == "__main__":
    unittest.main()
