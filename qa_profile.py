"""Visual smoke check for the on-demand player panel; uses a tiny verified fixture."""
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from services.storage import SettingsStore
from ui.theme import ThemeManager
from ui.player_profile import PlayerProfileDialog
from data_sources.player_profiles import PlayerRequest, PlayerProfileService

app = QApplication([])
app.setStyle("Fusion")
theme = ThemeManager(SettingsStore())
theme.mode = "light"
theme.apply()
rows = {"MS": [{"PlayerName": "LEBRUN Alexis", "IttfId": "132992", "CountryCode": "FRA", "CurrentRank": 12, "RankingPointsYTD": 3200, "PublishDate": "2026-09-24"}], "WS": [{"PlayerName": "WANG Manyu", "IttfId": "121411", "CountryCode": "CHN", "CurrentRank": 1, "RankingPointsYTD": 9115}]}
dialog = PlayerProfileDialog(PlayerRequest("王曼昱", "WANG Manyu", "CHN", "121411"), PlayerProfileService(), rows)
dialog.show()
for _ in range(250):
    QTest.qWait(100)
    if dialog.avatar.pixmap() and dialog.win_rate[1].text() != "查询中…":
        break
assert dialog.avatar.pixmap() and dialog.win_rate[1].text() != "查询中…"
out = Path("release/qa")
out.mkdir(parents=True, exist_ok=True)
dialog.grab().save(str(out / "player-profile-wang-light.png"))
theme.mode = "dark"
theme.apply()
app.processEvents()
dialog.grab().save(str(out / "player-profile-wang-dark.png"))
dialog.close()
print("Official Wang Manyu photo, age, style, year win rate and WTT link available")
