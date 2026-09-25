"""Render deterministic Qt UI fixtures for visual regression inspection."""
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtTest import QTest
from data_sources.majors import MajorsDataSource
from models import Match, STATUS_FINISHED, STATUS_LIVE
from services.storage import SettingsStore, FavoritesStore
from services.updater import Updater
from ui.main_window import MainWindow
from ui.match_card import MatchCard
from ui.theme import ThemeManager

app = QApplication([])
app.setStyle("Fusion")
theme = ThemeManager(SettingsStore())
theme.mode = "light"
theme.apply()
favorites = FavoritesStore()
window = MainWindow(Updater([]), theme, favorites)
window.resize(1100, 800)
window.show()
window._on_matches_changed(MajorsDataSource().get_matches())
out = Path("release/qa")
out.mkdir(parents=True, exist_ok=True)
window._open_detail("major:2751:女子团体")
app.processEvents()
assert window.detail_page.games_box.count() == 9
QTest.qWait(200)
window.grab().save(str(out / "team-light.png"))
theme.mode = "dark"
theme.apply()
app.processEvents()
window.grab().save(str(out / "team-dark.png"))
theme.mode = "light"
theme.apply()
m = Match("fixture", "WTT", "WTT Star Contender Astana 2026 · Men's Doubles", STATUS_FINISHED,
          datetime.now(), "YU Haiyang/TANG Yiren (CHN)", "CHIRITA Iulian/IONESCU Ovidiu (ROU)",
          score_a=3, score_b=1, sets=[(7,11),(11,9),(11,3),(15,13)])
card = MatchCard(m, favorites)
card.resize(860, 220)
card.show()
app.processEvents()
card.grab().save(str(out / "wtt-card.png"))
m.status = STATUS_LIVE
m.score_a = 1
m.score_b = 1
m.sets = [(7,11),(11,9)]
m.current_set = (6,4)
card.set_match(m, datetime.now())
app.processEvents()
assert card.score_strip.grid.count() == 11
card.grab().save(str(out / "live-card.png"))
card.close()
from data_sources.rankings import fetch_rankings
window.rankings_page._complete(fetch_rankings(), "")
window.rankings_page.refresh = lambda: None
window._on_nav_clicked(window._nav_keys["rankings"])
app.processEvents()
QTest.qWait(200)
assert window.rankings_page.table.rowCount() == 100
window.grab().save(str(out / "rankings-men.png"))
window.rankings_page.select("WS")
app.processEvents()
assert window.rankings_page.table.rowCount() == 100
window.grab().save(str(out / "rankings-women.png"))
theme.mode = "dark"
theme.apply()
app.processEvents()
window.grab().save(str(out / "rankings-dark.png"))
window.close()
print("UI render and transitions OK")
