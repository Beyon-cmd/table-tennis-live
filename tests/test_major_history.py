import unittest
from dataclasses import replace
from datetime import datetime, timedelta

from PySide6.QtWidgets import QApplication

from services.updater import Updater
from ui.main_window import MainWindow, MAJOR_HISTORY_SECTIONS
from ui.theme import ThemeManager
from models import Match
from data_sources.majors import MajorsDataSource


class _Favorites:
    def contains(self, match_id):
        return False


class MajorHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_three_categories_are_separate_and_details_work(self):
        settings = type("Settings", (), {"theme": "light"})()
        window = MainWindow(Updater([]), ThemeManager(settings), _Favorites())
        try:
            self.assertEqual(set(MAJOR_HISTORY_SECTIONS), {"奥运会", "世锦赛", "世界杯"})
            counts = {name: len(page.all_cards()) for name, page in window.major_history_pages.items()}
            self.assertEqual(counts, {"奥运会": 18, "世锦赛": 40, "世界杯": 43})
            window._on_league_toggled("majors", True)
            for category in MAJOR_HISTORY_SECTIONS:
                window._switch_major_category(category)
                self.assertIs(window._stack.currentWidget(), window.major_history_pages[category])
            window._switch_major_category("奥运会")
            match = window.major_history_pages["奥运会"].all_cards()[0]._match
            window._open_detail(match.id)
            self.assertEqual(window._detail_id, match.id)
            self.assertEqual(window.detail_page.score.text(), f"{match.score_a} : {match.score_b}")
            window._back_from_detail()
            self.assertIs(window._stack.currentWidget(), window.major_history_pages["奥运会"])
        finally:
            window.close()

    def test_official_current_match_automatically_switches_back_to_archive_after_finish(self):
        settings = type("Settings", (), {"theme": "light"})()
        window = MainWindow(Updater([]), ThemeManager(settings), _Favorites())
        try:
            window._on_league_toggled("majors", True)
            window._switch_major_category("世锦赛")
            self.assertIs(window._stack.currentWidget(), window.major_history_pages["世锦赛"])
            live = Match("official:1", "majors", "世界乒乓球锦标赛", "live",
                         datetime.now() - timedelta(minutes=2), "A", "B",
                         score_a=1, major_category="世锦赛")
            window._on_matches_changed([live])
            self.assertIs(window._stack.currentWidget(), window.major_current_pages["世锦赛"])
            self.assertEqual(len(window.major_current_pages["世锦赛"].all_cards()), 1)
            window._on_matches_changed([replace(live, status="finished", score_a=3)])
            self.assertIs(window._stack.currentWidget(), window.major_history_pages["世锦赛"])
            self.assertTrue(window.major_history_pages["世锦赛"].all_cards())
        finally:
            window.close()

    def test_future_official_feed_failure_marks_cached_match_stale(self):
        class Feed:
            category = "世界杯"
            calls = 0

            def get_matches(self):
                self.calls += 1
                if self.calls == 2:
                    raise RuntimeError("offline")
                return [Match("official:cup", "majors", "世界杯", "live",
                              datetime.now(), "A", "B", major_category=self.category)]

            def get_match_detail(self, match_id):
                return None

        source = MajorsDataSource((Feed(),))
        source._asian_games.matches = lambda: []
        first = source.get_matches()
        second = source.get_matches()
        self.assertFalse(first[0].data_stale)
        self.assertTrue(second[0].data_stale)
