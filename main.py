"""Table Tennis Live — 程序入口。

运行：python main.py
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication

from data_sources.cttsl import CTTSLDataSource
from data_sources.majors import MajorsDataSource
from data_sources.tleague import TLeagueDataSource
from data_sources.ttbl import TTBLDataSource
from data_sources.wtt import WTTDataSource
from services.storage import FavoritesStore, SettingsStore
from services.cloud_sync import CloudSyncManager
from services.updater import Updater
from ui.main_window import MainWindow
from ui.theme import ThemeManager


def _icon_path() -> str | None:
    if getattr(sys, "frozen", False):  # 打包后的资源在解压临时目录里
        base = Path(getattr(sys, "_MEIPASS", "."))
        path = base / "assets" / "icon.ico"
    else:
        path = Path(__file__).resolve().parent / "assets" / "icon.ico"
    return str(path) if path.exists() else None


def main() -> int:
    if "--self-test" in sys.argv:
        # Exercise the actual packaged Qt DLLs, platform plugin and widgets.
        # No network workers: a successful process exit must mean Qt ran.
        import json
        from PySide6.QtCore import qVersion
        app = QApplication(sys.argv)
        icon_path = _icon_path()
        assert icon_path is not None
        icon = QIcon(icon_path)
        assert not icon.isNull() and len(icon.availableSizes()) >= 7
        app.setWindowIcon(icon)
        theme = ThemeManager(SettingsStore())
        theme.apply()
        updater = Updater([])
        window = MainWindow(updater, theme, FavoritesStore(), settings=theme._settings)
        window.setWindowIcon(icon)
        assert not window.windowIcon().isNull()
        window.rankings_page.shutdown()  # Keep packaged self-test fully offline.
        window.show()
        window._on_matches_changed(MajorsDataSource().get_historical_matches())
        window._open_detail("major:590:男子单打")
        assert window.detail_page.score.text() == "4 : 1"
        assert window.detail_page.trend_chart._points
        assert not window.detail_page.trend_chart.grab().isNull()
        window._open_detail("major:2751:女子团体")
        assert window.detail_page.score.text() == "3 : 2"
        assert window.detail_page.games_box.count() == 9
        window._on_league_toggled("majors", True)
        assert set(window._major_buttons) == {"奥运会", "世锦赛", "世界杯", "亚运会"}
        window._switch_major_view(True)
        assert window._stack.currentWidget() is window.asian_draws_page
        window._switch_major_category("奥运会")
        assert window._stack.currentWidget() is window.major_history_pages["奥运会"]
        assert window.major_history_pages["奥运会"].all_cards()
        QTimer.singleShot(250, window.close)
        result = app.exec()
        report = sys.argv[sys.argv.index("--self-test") + 1]
        Path(report).write_text(json.dumps({"ok": result == 0, "qt": qVersion(),
                                           "major_count": len(window._matches),
                                           "icon_sizes": len(icon.availableSizes())}), encoding="utf-8")
        return result
    smoke = "--smoke" in sys.argv
    if smoke:
        print("SMOKE: app init", flush=True)
    app = QApplication(sys.argv)
    app.setApplicationName("Table Tennis Live")
    app.setOrganizationName("TableTennisLive")
    app.setStyle("Fusion")
    app.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont))
    icon = _icon_path()
    if icon:
        app.setWindowIcon(QIcon(icon))

    settings = SettingsStore()
    favorites = FavoritesStore()
    cloud = CloudSyncManager(favorites)
    theme = ThemeManager(settings)
    theme.apply()
    if smoke:
        print("SMOKE: theme applied", flush=True)

    # 离线模式：仅用于无网络环境下的自检（不抓取任何数据）
    if os.environ.get("TABLE_TENNIS_LIVE_OFFLINE") == "1":
        updater = Updater([CTTSLDataSource()])
    else:
        updater = Updater(
            [
                MajorsDataSource(),
                WTTDataSource(),
                TTBLDataSource(),
                TLeagueDataSource(),
                CTTSLDataSource(),
            ]
        )
    if smoke:
        print("SMOKE: updater created", flush=True)
    window = MainWindow(updater, theme, favorites, settings=settings, cloud=cloud)
    if icon:
        window.setWindowIcon(QIcon(icon))
    if os.environ.get("TABLE_TENNIS_LIVE_OFFLINE") == "1":
        window.rankings_page.shutdown()
    window.show()
    cloud.restore()
    updater.start()
    if smoke:
        print("SMOKE: window shown, updater started", flush=True)

    # 打包后的自检模式：3 秒后关闭窗口自动退出（会先停掉后台刷新线程）
    if smoke:
        print("SMOKE: quitting in 3s", flush=True)
        QTimer.singleShot(3000, window.close)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
