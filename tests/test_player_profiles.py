import unittest
from datetime import datetime
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from data_sources.player_profiles import PlayerRequest, PlayerProfileService, profile_url, resolve_from_rows, split_players, parse_player_details
from data_sources.wtt import WTTDataSource
from models import Match
from services.storage import FavoritesStore
from ui.match_card import MatchCard
from ui.player_profile import PlayerProfileDialog


ROWS = {"MS": [dict(PlayerName="LEBRUN Alexis", IttfId="132992", CountryCode="FRA", CurrentRank="12", RankingPointsYTD="3200", PublishDate="2026-09-24")], "WS": [dict(PlayerName="WANG Manyu", IttfId="121411", CountryCode="CHN", CurrentRank="2", RankingPointsYTD="7000")]}


class PlayerProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_official_id_and_safe_name_resolution(self):
        row = resolve_from_rows(PlayerRequest("亚历克西·勒布伦", "Alexis LEBRUN", "FRA", "132992"), ROWS)
        self.assertEqual(row["id"], "132992")
        self.assertEqual(row["rank"], "12")
        self.assertEqual(resolve_from_rows(PlayerRequest("Alexis LEBRUN", country="GER"), ROWS), None)
        self.assertEqual(profile_url("not-an-id"), "")
        self.assertEqual(split_players("A / B"), ["A", "B"])
        ambiguous = {"MS": ROWS["MS"] + [dict(ROWS["MS"][0], IttfId="999999")], "WS": ROWS["WS"]}
        self.assertIsNone(resolve_from_rows(PlayerRequest("Alexis LEBRUN"), ambiguous))

    def test_wtt_source_keeps_individual_id_not_doubles_team_id(self):
        source = WTTDataSource()
        try:
            self.assertEqual(source._competitor_player_id({"Code":"132992", "Type":"A"}), "132992")
            self.assertEqual(source._competitor_player_id({"Code":"999", "Composition":{"Athlete":[{"Code":"1"},{"Code":"2"}]}}), "")
            self.assertEqual(source._card_player_ids({"competitiors":[{"players":[{"playerId":"132992"}]},{"players":[{"playerId":"121411"}]}]}), ["132992", "121411"])
        finally:
            source._client.close()

    def test_match_name_click_does_not_open_match(self):
        favorites = type("Favorites", (), {"contains": lambda self, mid: False})()
        match = Match("x", "WTT", "Test", "finished", datetime.now(), "LEBRUN Alexis (FRA)", "WANG Manyu (CHN)", player_a_id="132992")
        card = MatchCard(match, favorites)
        card.show()
        self.app.processEvents()
        players, matches = [], []
        card.player_clicked.connect(players.append)
        card.clicked.connect(matches.append)
        QTest.mouseClick(card.player_a, Qt.MouseButton.LeftButton)
        self.assertEqual(players[0].player_id, "132992")
        self.assertEqual(matches, [])
        card.close()

    def test_dialog_uses_verified_result_and_link(self):
        service = PlayerProfileService()
        with patch.object(service, "resolve", return_value={"id":"132992", "name":"LEBRUN Alexis", "country":"FRA", "rank":"12", "points":"3200", "event":"MS", "published":"2026-09-24"}):
            dialog = PlayerProfileDialog(PlayerRequest("LEBRUN Alexis", player_id="132992"), service)
            dialog.show()
            for _ in range(20):
                QTest.qWait(10)
                if dialog.rank[1].text() == "#12":
                    break
            self.assertEqual(dialog.rank[1].text(), "#12")
            self.assertTrue(dialog.website.isEnabled())
            dialog.close()

    def test_official_profile_fields_and_untrusted_image_rejected(self):
        player = {"IttfId":"121411", "PlayerName":"WANG Manyu", "CountryCode":"CHN", "CountryName":"China", "Age":"27", "Handedness":"Right Hand", "Grip":"Shakehand", "Gender":"F", "HeadShot":"https://evil.example/image.png"}
        stats = {"IttfId":"121411", "SubeventCode":"WS", "current_year_total_wins":"22", "current_year_total_matches":"28"}
        payload = {"additional_data":{"PlayerData":[player],"StatsData":[stats]},"ranking":1,"rankingPoints":9115}
        self.assertEqual(parse_player_details(payload, "121411")["win_rate"], 79)
        self.assertEqual(parse_player_details(payload, "121411")["image_url"], "")
        self.assertEqual(parse_player_details(payload, "999999"), {})
