import unittest
from dataclasses import replace
from datetime import datetime
from unittest.mock import patch
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget, QLabel
from ui.rankings import RankingsPage
from ui.motion import TransitionStack, SmoothScrollArea
from data_sources.rankings import parse_rankings
from models import Match
from ui.match_card import MatchCard
from ui.match_detail import MatchDetailPage


class MemoryStore:
    def __init__(self, *args):
        self._data = {}
    def save(self):
        pass


class ModernUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.store_patch = patch("ui.rankings.JsonStore", MemoryStore)
        self.store_patch.start()
        self.data = parse_rankings({"Result": [dict(SubEventCode=event, PlayerName="WANG Chuqin", CurrentRank="1", RankingPointsYTD="8000") for event in ("MS", "WS")]})

    def tearDown(self):
        self.store_patch.stop()

    def test_stale_score_warning_survives_timer_and_clears_on_recovery(self):
        class Favorites:
            def contains(self, _match_id):
                return False

        fresh = Match("m", "WTT", "Test", "live", datetime.now(), "A", "B", score_a=2)
        stale = replace(fresh, data_stale=True)
        card = MatchCard(fresh, Favorites())
        detail = MatchDetailPage(Favorites())
        card.set_match(stale, datetime.now())
        detail.set_match(stale)
        card.refresh_time(datetime.now())
        detail.refresh_time(datetime.now())
        self.assertIn("旧数据", card.badge.text())
        self.assertIn("旧数据", detail.badge.text())
        self.assertIn("未重新核对", card.meta.text())
        card.set_match(fresh, datetime.now())
        detail.set_match(fresh)
        self.assertEqual(card.badge.text(), "● LIVE")
        self.assertEqual(detail.badge.text(), "● LIVE")
        card.deleteLater()
        detail.deleteLater()

    def test_unchanged_no_table_rebuild_and_failure_preserves_rows(self):
        page = RankingsPage()
        page._complete(self.data, "")
        first = page.table.item(0, 1)
        page._complete(self.data, "")
        self.assertIs(page.table.item(0, 1), first)
        page._complete(None, "offline")
        self.assertIs(page.table.item(0, 1), first)
        self.assertTrue(page._timer.isActive())
        self.assertEqual(page._timer.interval(), 60000)
        page.shutdown()
        self.assertFalse(page._timer.isActive())
        page.deleteLater()

    def test_timer_fetches_and_does_not_overlap(self):
        page = RankingsPage()
        with patch("ui.rankings.fetch_rankings", return_value=self.data) as fetch:
            page.refresh()
            page.refresh()
            for _ in range(30):
                QTest.qWait(10)
                if not page._busy:
                    break
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(page.table.rowCount(), 1)
            page._timer.setInterval(20)
            page._timer.start()
            QTest.qWait(100)
            self.assertGreaterEqual(fetch.call_count, 2)
            page.shutdown()
        page.deleteLater()

    def test_transition_finishes_and_rapid_switch_is_safe(self):
        stack = TransitionStack()
        a, b = QWidget(), QWidget()
        stack.addWidget(a)
        stack.addWidget(b)
        stack.show()
        self.app.processEvents()
        stack.setCurrentWidget(b)
        stack.setCurrentWidget(a)
        QTest.qWait(200)
        self.assertIs(stack.currentWidget(), a)
        self.assertFalse(stack._overlay.isVisible())
        stack.close()

    def test_smooth_wheel_reaches_target(self):
        area = SmoothScrollArea()
        content = QLabel("Long list")
        content.setFixedSize(200, 2000)
        area.setWidget(content)
        area.resize(300, 300)
        area.show()
        self.app.processEvents()
        event = QWheelEvent(QPointF(30,30), QPointF(30,30), QPoint(), QPoint(0,-120), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        area.wheelEvent(event)
        QTest.qWait(240)
        self.assertEqual(area.verticalScrollBar().value(), 108)
        area.close()
