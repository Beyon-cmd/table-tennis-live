import unittest
from dataclasses import replace
from datetime import datetime

from PySide6.QtWidgets import QApplication

from models import Match, ScoreEvent
from services.score_trend import ScoreTrendStore
from ui.score_trend import ScoreTrendWidget


class ScoreTrendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def match(self, **changes):
        original = Match("wtt:1", "WTT", "Test", "live", datetime.now(), "A", "B",
                         current_set=(6, 4), score_known=True)
        return replace(original, **changes)

    def test_only_observed_scores_no_interpolated_points(self):
        store = ScoreTrendStore()
        first = self.match()
        store.observe(first)
        store.observe(self.match(current_set=(9, 5)))
        points = store.points(first)
        self.assertEqual([(p.score_a, p.score_b) for p in points], [(6, 4), (9, 5)])
        self.assertEqual(points[-1].streak_count, 0)
        store.observe(self.match(current_set=(9, 5), data_stale=True))
        self.assertEqual(len(store.points(first)), 2)

    def test_game_point_and_streak_require_evidence(self):
        store = ScoreTrendStore()
        for a, b in ((8, 9), (9, 9), (10, 9), (11, 9)):
            store.observe(self.match(current_set=(a, b)))
        points = store.points(self.match(current_set=(11, 9)))
        self.assertEqual(points[2].game_point_player, 0)
        self.assertIsNone(points[-1].game_point_player)  # 局已结束
        self.assertEqual(points[-1].streak_count, 3)
        self.assertEqual(points[-1].streak_player, 0)

    def test_official_pause_and_match_point_only_when_supplied(self):
        store = ScoreTrendStore()
        match = self.match(current_set=(10, 9), sets=[(11, 8), (11, 7)],
                           winning_sets=3,
                           score_events=[ScoreEvent(3, 10, 9, "timeout")])
        store.observe(match)
        current = store.points(match)[-1]
        self.assertIn("timeout", current.official_events)
        self.assertEqual(current.game_point_player, 0)
        self.assertEqual(current.match_point_player, 0)
        without_format = replace(match, winning_sets=None)
        self.assertIsNone(store.points(without_format)[-1].match_point_player)

    def test_finished_match_has_endpoints_not_fictional_rallies_and_renders(self):
        store = ScoreTrendStore()
        match = self.match(status="finished", current_set=None, sets=[(11, 7), (9, 11), (11, 6)])
        store.observe(match)
        points = store.points(match)
        self.assertEqual(len(points), 3)
        self.assertTrue(all(p.final for p in points))
        chart = ScoreTrendWidget()
        chart.resize(720, 230)
        chart.set_points(points)
        self.assertFalse(chart.grab().isNull())
        chart.deleteLater()
