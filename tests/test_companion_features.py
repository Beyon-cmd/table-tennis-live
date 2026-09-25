import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from models import Match, STATUS_FINISHED, STATUS_LIVE, STATUS_UPCOMING
from services.calendar_export import build_ics, start_utc, time_labels
from services.match_alerts import MatchAlertTracker
from services.storage import SettingsStore
from services.updater import Updater
from ui.main_window import MainWindow
from data_sources.tleague import TLeagueDataSource
from ui.mini_score import MiniScoreWindow
from ui.theme import ThemeManager


class CompanionFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.start = datetime(2026, 9, 25, 18, 0)
        self.match = Match("wtt:1", "WTT", "测试赛 · 男单", STATUS_UPCOMING,
                           self.start, "甲", "乙", score_known=False)

    def test_opt_in_alerts_are_transition_based_and_not_duplicated(self):
        tracker = MatchAlertTracker()
        options = {"start": True, "score": True, "final": True}
        self.assertEqual(tracker.update(self.match, True, options), [])
        near = self.start - timedelta(minutes=4)
        self.assertEqual(tracker.due(self.match, near, options).kind, "start")
        self.assertIsNone(tracker.due(self.match, near, options))
        live = replace(self.match, status=STATUS_LIVE, score_known=True, score_a=0)
        self.assertEqual(tracker.update(live, True, options), [])  # pre-start reminder already sent
        scored = replace(live, score_a=1, sets=[(11, 8)])
        self.assertEqual([e.kind for e in tracker.update(scored, True, options)], ["score"])
        self.assertEqual(tracker.update(scored, True, options), [])
        final = replace(scored, status=STATUS_FINISHED, score_a=3)
        self.assertEqual([e.kind for e in tracker.update(final, True, options)], ["final"])
        self.assertEqual(tracker.update(final, True, options), [])

    def test_unfollowed_and_stale_matches_do_not_notify(self):
        tracker = MatchAlertTracker()
        enabled = {"start": True, "score": True, "final": True}
        tracker.update(self.match, False, enabled)
        self.assertEqual(tracker.update(replace(self.match, status=STATUS_LIVE), False, enabled), [])
        tracker.update(self.match, True, enabled)
        self.assertEqual(tracker.update(replace(self.match, status=STATUS_LIVE, data_stale=True), True, enabled), [])

    def test_calendar_uses_utc_escapes_and_crlf(self):
        aware = replace(self.match, start_time=datetime(2026, 9, 25, 18,
                                                       tzinfo=timezone(timedelta(hours=8))),
                        competition="测试赛,男单;决赛")
        data = build_ics(aware, datetime(2026, 9, 24, tzinfo=timezone.utc))
        text = data.decode("utf-8")
        self.assertIn("DTSTART:20260925T100000Z\r\n", text)
        self.assertIn("DTEND:20260925T120000Z\r\n", text)
        self.assertIn("测试赛\\,男单\\;决赛", text)
        self.assertIn("北京时间 2026-09-25 18:00", time_labels(aware))
        self.assertTrue(all(len(line.encode("utf-8")) <= 75 for line in text.split("\r\n")))
        self.assertEqual(start_utc(aware).hour, 10)
        with self.assertRaises(ValueError):
            build_ics(replace(self.match, status=STATUS_LIVE))

    def test_tleague_japan_time_is_normalized_before_calendar_export(self):
        html = ('<tr>2026年9月25日(金) 16:00'
                '<span class="d-none d-lg-inline">Home</span>'
                '<span class="d-none d-lg-inline">Away</span>'
                '<a href="detail.php?id=123">详情</a></tr>')
        row = TLeagueDataSource._parse_html(html)[0]
        league_match = replace(self.match, source="T.League", start_time=row["start"])
        self.assertEqual(start_utc(league_match),
                         datetime(2026, 9, 25, 7, tzinfo=timezone.utc))

    def test_mini_score_follows_live_and_favorites(self):
        class Favorites:
            def contains(self, match_id):
                return match_id == "fav"
        mini = MiniScoreWindow(Favorites())
        try:
            live = replace(self.match, id="live", status=STATUS_LIVE,
                           score_known=True, score_a=2, score_b=1)
            favorite = replace(self.match, id="fav")
            ignored = replace(self.match, id="other")
            mini.set_matches([ignored, live, favorite])
            self.assertEqual(mini.selector.count(), 2)
            mini.selector.setCurrentIndex(mini.selector.findData("live"))
            self.assertIn("2 : 1", mini.score.text())
            self.assertIn("LIVE", mini.score.text())
        finally:
            mini.close()

    def test_alert_preferences_persist_and_main_window_controls_open(self):
        with TemporaryDirectory() as folder, patch("services.storage.DATA_DIR", Path(folder)):
            settings = SettingsStore()
            self.assertFalse(settings.alert_enabled("score"))
            settings.set_alert("score", True)
            self.assertTrue(SettingsStore().alert_enabled("score"))
            class Favorites:
                def contains(self, _match_id):
                    return False
            window = MainWindow(Updater([]), ThemeManager(settings), Favorites(), settings=settings)
            try:
                window._on_matches_changed([self.match])
                window._toggle_mini_score()
                self.assertTrue(window._mini_score.isVisible())
                window._toggle_mini_score()
                window.detail_page.set_match(self.match)
                self.assertFalse(window.detail_page.calendar_button.isHidden())
            finally:
                window.close()


if __name__ == "__main__":
    unittest.main()
