import unittest
from unittest.mock import patch
from data_sources.wtt_draws import parse_draws, fetch_events
from datetime import datetime
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from ui.wtt_draws import WTTDrawsPage, DrawCard
from ui.modern_select import ModernSelect
from ui.theme import ThemeManager


def place(name, previous="", score=None, winner=""):
    return {"Code": name, "Result": score, "Wlt": winner, "PreviousUnit": {"Unit": previous},
            "Competitor": {"Description": {"TeamName": name}, "Organization": "CHN"}}


def fixture():
    return {"Competition": {"Bracket": [{"Code": "MAIN", "BracketItems": [
        {"Code":"FNL-", "BracketItem": {"Code":"final", "CompetitorPlace":[place("TBD","semi1"),place("TBD","semi2")]}},
        {"Code":"SFNL", "BracketItem": [
            {"Code":"semi2", "Order":2,"CompetitorPlace":[place("C",score="2"),place("D",score="3",winner="W")],"Result":"2-3 (11:8,9:11,11:5,8:11,7:11)"},
            {"Code":"semi1", "Order":1,"CompetitorPlace":[place("A",score="0",winner="W"),place("BYE")]}]}]}]}}


class DrawTests(unittest.TestCase):
    def test_events_keep_original_tiers(self):
        day = datetime.now().isoformat()
        rows = [{"eventId":i,"eventName":name,"startDateTime":day,"endDateTime":day}
                for i,name in enumerate(["WTT Feeder Example", "WTT Youth Contender Example", "WTT Contender Example", "China Smash 2026"])]
        with patch("data_sources.wtt_draws.httpx.get") as get:
            get.return_value.json.return_value = rows
            self.assertEqual({e["id"] for e in fetch_events()},{2,3})

    def test_official_predecessors_and_byes(self):
        data = parse_draws(fixture())
        self.assertEqual([r["code"] for r in data["MAIN"]],["SFNL","FNL"])
        first = data["MAIN"][0]["matches"][0]
        self.assertEqual(first["id"],"semi1")
        self.assertTrue(first["bye"])
        self.assertEqual(first["players"][0]["score"],"—")
        self.assertEqual(data["MAIN"][1]["matches"][0]["players"][0]["previous"],"semi1")
        self.assertEqual(len(data["MAIN"][0]["matches"][1]["sets"]),5)

    def test_empty_and_malformed(self):
        self.assertEqual(parse_draws(None),{})
        self.assertEqual(parse_draws({"Competition": {"Bracket":[]}}),{})
        with self.assertRaises(ValueError):
            parse_draws({"error":"bad"})

    def test_padded_zero_set_removed(self):
        raw = fixture()
        raw["Competition"]["Bracket"][0]["BracketItems"][1]["BracketItem"][0]["Result"] += " (0:0)"
        games = parse_draws(raw)["MAIN"][0]["matches"][1]["sets"]
        self.assertNotIn((0,0),games)

    def test_modern_selector_and_zoom_bounds(self):
        app = QApplication.instance() or QApplication([])
        select = ModernSelect("选择赛事",searchable=True)
        changed = []
        select.currentIndexChanged.connect(changed.append)
        for index in range(12):
            select.addItem(f"WTT赛事 {index}",index)
        select.resize(350,50)
        select.show()
        select.open_popup()
        app.processEvents()
        self.assertTrue(select._popup.isVisible())
        search = select._popup.findChild(__import__("PySide6.QtWidgets",fromlist=["QLineEdit"]).QLineEdit)
        search.setText("11")
        app.processEvents()
        self.assertEqual(sum(b.isVisible() for b in select._popup.findChildren(__import__("PySide6.QtWidgets",fromlist=["QPushButton"]).QPushButton)),1)
        select._choose(11,select._popup)
        self.assertEqual(select.currentData(),11)
        self.assertEqual(changed[-1],11)
        select.close()

        settings = type("Settings",(),{"theme":"light"})()
        page = WTTDrawsPage(ThemeManager(settings))
        page.canvas.set_zoom(20)
        self.assertEqual(page.canvas.zoom,2.5)
        page.canvas.set_zoom(0.01)
        self.assertEqual(page.canvas.zoom,0.35)
        page.canvas.set_zoom(1)
        self.assertEqual(page.zoom_reset.text(),"100%")
        page.shutdown()

    def test_stale_response_error_and_click(self):
        app = QApplication.instance() or QApplication([])
        settings = type("Settings",(),{"theme":"light"})()
        theme = ThemeManager(settings)
        page = WTTDrawsPage(theme)
        page._events = [{"id":1}]
        page.event_combo.blockSignals(True)
        page.event_combo.addItem("Fixture",1)
        page.event_combo.blockSignals(False)
        with patch.object(page,"refresh") as refresh:
            page.complete((2,"MSINGLES"),parse_draws(fixture()),"")
            refresh.assert_called_once()
        self.assertEqual(page._data,{})
        page.complete(page.key(),parse_draws(fixture()),"")
        items = page.canvas.scene().items()
        page.complete(page.key(),None,"offline")
        self.assertEqual(len(page.canvas.scene().items()),len(items))
        with patch.object(page,"refresh"):
            page.resize(1100,650)
            page.show()
            app.processEvents()
            cards = [i for i in page.canvas.scene().items() if isinstance(i,DrawCard)]
            clicked=[]
            cards[0].callback=clicked.append
            point=page.canvas.mapFromScene(cards[0].sceneBoundingRect().center())
            page.canvas.ensureVisible(cards[0])
            app.processEvents()
            point=page.canvas.mapFromScene(cards[0].sceneBoundingRect().center())
            QTest.mouseClick(page.canvas.viewport(),Qt.MouseButton.LeftButton,pos=point)
            self.assertEqual(len(clicked),1)
        page.shutdown()
        page.close()
