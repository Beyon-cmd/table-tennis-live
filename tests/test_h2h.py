import unittest
from datetime import datetime, timedelta

from models import Match, STATUS_FINISHED, STATUS_UPCOMING
from services.h2h import build_h2h
from PySide6.QtWidgets import QApplication
from ui.match_detail import MatchDetailPage


class H2HTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 25, 18)
        self.target = Match("fixture", "WTT", "WTT Champions · Men's Singles",
                            STATUS_UPCOMING, self.now, "樊振东", "张继科",
                            player_a_raw="Fan Zhendong", player_b_raw="Zhang Jike",
                            player_a_id="1", player_b_id="2")

    def result(self, mid, a, b, score_a, score_b, **kwargs):
        return Match(mid, "WTT", "WTT Champions · Men's Singles", STATUS_FINISHED,
                     self.now - timedelta(days=int(mid[-1])), a, b,
                     score_a=score_a, score_b=score_b, **kwargs)

    def test_orientation_last_five_and_set_totals(self):
        rows = [
            self.result("m1", "樊振东", "张继科", 3, 1,
                        player_a_id="1", player_b_id="2"),
            self.result("m2", "张继科", "樊振东", 3, 2,
                        player_a_id="2", player_b_id="1"),
            self.result("m3", "Fan Zhendong", "Zhang Jike", 4, 0),
        ]
        report = build_h2h(self.target, rows + [rows[0]])
        self.assertEqual((report.wins_a, report.wins_b), (2, 1))
        self.assertEqual((report.sets_a, report.sets_b), (9, 4))
        self.assertEqual([m.match_id for m in report.meetings], ["m1", "m2", "m3"])
        self.assertEqual((report.competitions[0].meetings,
                          report.competitions[0].wins_a), (3, 2))

    def test_unverified_and_other_pairs_do_not_count(self):
        valid = self.result("m1", "樊振东", "张继科", 3, 0,
                            player_a_id="1", player_b_id="2")
        wrong_id = self.result("m2", "樊振东", "张继科", 3, 0,
                               player_a_id="9", player_b_id="2")
        no_score = self.result("m3", "樊振东", "张继科", 0, 0)
        doubles = self.result("m4", "樊振东/马龙", "张继科/王皓", 3, 0)
        report = build_h2h(self.target, [valid, wrong_id, no_score, doubles])
        self.assertEqual(len(report.meetings), 1)

    def test_empty_is_not_inferred_as_zero_career_meetings(self):
        self.assertEqual(build_h2h(self.target, []).meetings, ())
        team = Match("team", "WTT", "男子团体", STATUS_UPCOMING,
                     self.now, "中国", "德国")
        self.assertFalse(build_h2h(team, []).eligible)

    def test_prematch_panel_renders_and_hides_after_start(self):
        app = QApplication.instance() or QApplication([])
        favorites = type("Favorites", (), {"contains": lambda self, mid: False})()
        page = MatchDetailPage(favorites)
        try:
            page.set_match(self.target)
            report = build_h2h(self.target, [self.result("m1", "樊振东", "张继科", 3, 1)])
            page.set_h2h_report(report)
            self.assertFalse(page.h2h_container.isHidden())
            texts = [page.h2h_box.itemAt(i).widget().text()
                     for i in range(page.h2h_box.count())]
            self.assertTrue(any("1 胜 : 0 胜" in text for text in texts))
            from dataclasses import replace
            page.set_match(replace(self.target, status="live"))
            self.assertTrue(page.h2h_container.isHidden())
        finally:
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
