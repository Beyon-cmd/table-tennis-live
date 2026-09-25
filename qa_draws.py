"""Network-backed visual check with the official Astana draw, not mock players."""
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog
from data_sources.wtt_draws import fetch_draws
from services.storage import FavoritesStore, SettingsStore
from services.updater import Updater
from ui.theme import ThemeManager
from ui.main_window import MainWindow

app=QApplication([])
app.setStyle("Fusion")
theme=ThemeManager(SettingsStore())
theme.mode="light"
theme.apply()
window=MainWindow(Updater([]),theme,FavoritesStore())
window.rankings_page.shutdown()
window.resize(1280,820)
page=window.draws_page
data=fetch_draws(3254,"MSINGLES")
with patch.object(page,"refresh"):
    page._events=[{"id":3254}]
    page.event_combo.blockSignals(True)
    page.event_combo.addItem("WTT Star Contender Astana 2026",3254)
    page.event_combo.blockSignals(False)
    page.complete(page.key(),data,"")
    page.stage.setCurrentIndex(page.stage.findData("PREL"))
    window.show()
    window._on_league_toggled("WTT",True)
    window._switch_wtt_tab(True)
    QTest.qWait(250)
    out=Path("release/qa")
    out.mkdir(parents=True,exist_ok=True)
    window.grab().save(str(out/"draws-light.png"))
    page.event_combo.open_popup()
    app.processEvents()
    page.event_combo._popup.grab().save(str(out/"draws-selector.png"))
    page.event_combo._popup.close()
    page.canvas.set_zoom(0.7)
    app.processEvents()
    window.grab().save(str(out/"draws-zoom70.png"))
    page.canvas.set_zoom(1)
    def inspect_dialog():
        modal = app.activeModalWidget()
        assert isinstance(modal,QDialog)
        modal.grab().save(str(out/"draws-detail.png"))
        modal.accept()
    QTimer.singleShot(120,inspect_dialog)
    page.open_match(data["PREL"][0]["matches"][1])
    theme.mode="dark"
    theme.apply()
    theme.changed.emit()
    app.processEvents()
    window.grab().save(str(out/"draws-dark.png"))
    window._switch_wtt_tab(False)
    assert window._stack.currentWidget() is window.home_page
    window._switch_wtt_tab(True)
    assert page.stage.currentData()=="PREL"
window.close()
print("Official Astana draw UI, theme and original-list navigation OK")
