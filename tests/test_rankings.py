import unittest
from data_sources.rankings import parse_rankings
from ui.flags import player_html, flag_path


class RankingTests(unittest.TestCase):
    def test_singles_only_sorted(self):
        rows = [dict(SubEventCode=code, CurrentRank=str(rank), RankingPointsYTD="200", PlayerName="Example")
                for code, rank in [("MS", 2), ("MDI", 1), ("WS", 1), ("MS", 1)]]
        result = parse_rankings({"Result": rows})
        self.assertEqual([r["rank"] for r in result["MS"]], [1, 2])
        self.assertEqual(len(result["WS"]), 1)

    def test_incomplete_data_rejected(self):
        with self.assertRaises(ValueError):
            parse_rankings({"Result": []})

    def test_flags_escape_unknown_and_paths(self):
        self.assertIsNone(flag_path("../CHN"))
        self.assertEqual(player_html("<unknown> (ZZZ)"), "&lt;unknown&gt; (ZZZ)")
        self.assertIsNotNone(flag_path("CHN"))
        self.assertIn("<img", player_html("王楚钦 (CHN)"))
