"""主题：浅色 / 深色 / 跟随系统，MSN / Fluent 风格配色。"""
from __future__ import annotations

from string import Template

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from services.storage import SettingsStore

LIGHT = {
    "WINDOW": "#F3F6FB",
    "WINDOW_ALT": "#EDF2F8",
    "CARD": "#FFFFFF",
    "CARD_HOVER": "#FAFBFD",
    "SIDEBAR": "#FFFFFF",
    "BORDER": "#E4E6E8",
    "HOVER": "#F0F1F3",
    "SELECTED": "#E5F1FB",
    "TEXT": "#17263C",
    "TEXT_SEC": "#64748B",
    "ACCENT": "#2563EB",
    "ACCENT_SOFT": "#E5F1FB",
    "LIVE_BG": "#FDECEA",
    "LIVE_TEXT": "#C42B1C",
    "FINAL_BG": "#F0F1F2",
    "FINAL_TEXT": "#616161",
    "INPUT": "#FFFFFF",
    "SHADOW": QColor(15, 20, 25, 22),
}

DARK = {
    "WINDOW": "#101827",
    "WINDOW_ALT": "#172236",
    "CARD": "#1B293E",
    "CARD_HOVER": "#22344D",
    "SIDEBAR": "#131E30",
    "BORDER": "#2C3B52",
    "HOVER": "#343434",
    "SELECTED": "#1F3A4C",
    "TEXT": "#F5F5F5",
    "TEXT_SEC": "#ADADAD",
    "ACCENT": "#4CC2FF",
    "ACCENT_SOFT": "#1F3A4C",
    "LIVE_BG": "#402325",
    "LIVE_TEXT": "#FF7A70",
    "FINAL_BG": "#383838",
    "FINAL_TEXT": "#9E9E9E",
    "INPUT": "#2B2B2B",
    "SHADOW": QColor(0, 0, 0, 70),
}

QSS = """
QWidget { background: transparent; color: $TEXT; font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 14px; }
QFrame#RankingHero { background: $CARD; border: 1px solid $BORDER; border-radius: 16px; }
QLabel#HeroTitle { font-size: 25px; font-weight: 700; color: $TEXT; }
QLabel#HeroCaption { font-size: 12px; color: $TEXT_SEC; }
QLabel#Podium { background: $ACCENT_SOFT; color: $ACCENT; border-radius: 10px; padding: 14px; font-size: 14px; font-weight: 600; }
QMainWindow { background: $WINDOW; }
QDialog { background: $WINDOW; }
QGraphicsView#DrawCanvas { border: 1px solid $BORDER; border-radius: 12px; background: $WINDOW; }
QPushButton#ModernSelectButton { background: $CARD; color: $TEXT; border: 1px solid $BORDER; border-radius: 10px; padding: 10px 14px; text-align: left; }
QPushButton#ModernSelectButton:hover, QPushButton#ModernSelectButton:focus { border-color: $ACCENT; background: $CARD_HOVER; }
QFrame#ModernSelectPopup { background: $CARD; border: 1px solid $BORDER; border-radius: 12px; }
QWidget#SelectorList { background: $CARD; }
QLineEdit#SelectorSearch { background: $INPUT; border: 1px solid $BORDER; border-radius: 8px; padding: 8px 12px; color: $TEXT; }
QLineEdit#SelectorSearch:focus { border-color: $ACCENT; }
QPushButton#SelectorOption { background: transparent; color: $TEXT; border: none; border-radius: 8px; padding: 8px 12px; text-align: left; }
QPushButton#SelectorOption:hover { background: $HOVER; }
QPushButton#SelectorOption[selected="true"] { background: $ACCENT_SOFT; color: $ACCENT; font-weight: 600; }
QPushButton#ZoomButton { background: $CARD; color: $TEXT; border: 1px solid $BORDER; border-radius: 8px; padding: 7px 11px; min-width: 44px; }
QPushButton#ZoomButton:hover { border-color: $ACCENT; color: $ACCENT; }
QWidget#ScrollCorner, QAbstractScrollArea::corner { background: $WINDOW; border: none; }
QPushButton#RankingButton { background: $CARD; color: $TEXT; border: 1px solid $BORDER; border-radius: 7px; padding: 9px 18px; }
QPushButton#RankingButton:checked { background: $ACCENT_SOFT; color: $ACCENT; border-color: $ACCENT; }
QPushButton#RankingButton:hover { background: $HOVER; }
QTableWidget#RankingTable { background: $CARD; alternate-background-color: $WINDOW; color: $TEXT; border: 1px solid $BORDER; selection-background-color: $SELECTED; selection-color: $TEXT; }
QHeaderView::section { background: $WINDOW_ALT; color: $TEXT_SEC; padding: 10px; border: none; font-weight: 600; }
QWidget#Root { background: $WINDOW; }
QWidget#Sidebar { background: $SIDEBAR; border-right: 1px solid $BORDER; }
QWidget#TopBar { background: $WINDOW; border-bottom: 1px solid $BORDER; }
QWidget#TopTools { background: $CARD; border: 1px solid $BORDER; border-radius: 11px; }
QPushButton#TopToolButton { background: transparent; color: $TEXT_SEC; border: none;
    border-radius: 8px; padding: 8px 11px; font-size: 13px; font-weight: 600; min-height: 22px; }
QPushButton#TopToolButton:hover { background: $HOVER; color: $TEXT; }
QPushButton#TopToolButton[active="true"] { background: $ACCENT_SOFT; color: $ACCENT; }
QPushButton#TopToolButton:disabled { color: $TEXT_SEC; }
QPushButton#TopToolButton::menu-indicator { image: none; width: 0px; }
QPushButton#TopRefreshButton { background: $CARD; color: $ACCENT; border: 1px solid $BORDER;
    border-radius: 10px; min-width: 40px; min-height: 40px; padding: 0px; font-size: 21px; }
QPushButton#TopRefreshButton:hover { background: $ACCENT_SOFT; border-color: $ACCENT; }
QWidget#MiniScoreWindow { background: $CARD; border: 1px solid $BORDER; border-radius: 12px; }
QLabel#MiniTitle { color: $TEXT; font-size: 16px; font-weight: 700; }
QLabel#MiniMeta { color: $TEXT_SEC; font-size: 11px; }
QLabel#MiniPlayers { color: $TEXT; font-size: 15px; font-weight: 600; }
QLabel#MiniScore { color: $ACCENT; background: $ACCENT_SOFT; border-radius: 10px;
    padding: 12px; font-size: 20px; font-weight: 700; }
QComboBox#MiniSelector { background: $INPUT; color: $TEXT; border: 1px solid $BORDER;
    border-radius: 8px; padding: 7px 10px; min-height: 23px; }
QComboBox#MiniSelector:hover { border-color: $ACCENT; }
QScrollArea { background: transparent; border: none; }
QWidget#FeedContainer, QWidget#DetailContainer { background: transparent; }
QLabel#Brand { font-size: 16px; font-weight: 700; color: $TEXT; }
QLabel#PageTitle { font-size: 22px; font-weight: 700; color: $TEXT; padding: 8px 0; }
QLabel#NavGroupTitle { color: $TEXT_SEC; font-size: 12px; font-weight: 600; }
QLabel#Divider { background: $BORDER; min-height: 1px; max-height: 1px; }
QLabel#SectionTitle { font-size: 16px; font-weight: 700; color: $TEXT; }
QLabel#SectionCount { color: $TEXT_SEC; font-size: 13px; }
QLabel#Competition { color: $TEXT_SEC; font-size: 12px; font-weight: 600; }
QLabel#PlayerName { font-size: 15px; font-weight: 600; color: $TEXT; }
QLabel#PlayerLink { font-size: 15px; font-weight: 600; color: $TEXT; }
QLabel#PlayerLink:hover { color: $ACCENT; text-decoration: underline; }
QFrame#ProfileHero { background: $CARD; border: 1px solid $BORDER; border-radius: 16px; }
QLabel#ProfileAvatar { background: $ACCENT_SOFT; color: $ACCENT; border-radius: 14px; font-size: 15px; }
QLabel#ProfileOverline { color: $ACCENT; font-size: 11px; font-weight: 700; }
QLabel#ProfileName { color: $TEXT; font-size: 28px; font-weight: 700; }
QLabel#ProfileSecondary { color: $TEXT_SEC; font-size: 14px; }
QLabel#ProfileFact { color: $TEXT; font-size: 15px; padding-top: 4px; }
QFrame#ProfileStat { background: $CARD; border: 1px solid $BORDER; border-radius: 12px; }
QLabel#ProfileStatLabel { color: $TEXT_SEC; font-size: 12px; }
QLabel#ProfileStatValue { color: $ACCENT; font-size: 24px; font-weight: 700; }
QLabel#ProfileNote { color: $TEXT_SEC; font-size: 13px; }
QPushButton#ProfileAction { background: $ACCENT; color: white; border: none; border-radius: 9px; padding: 10px 16px; font-weight: 600; }
QPushButton#ProfileAction:hover { background: $TEXT; }
QPushButton#ProfileAction:disabled { background: $BORDER; color: $TEXT_SEC; }
QMenu { background: $CARD; color: $TEXT; border: 1px solid $BORDER; border-radius: 8px; padding: 5px; }
QMenu::item { padding: 8px 22px; border-radius: 6px; }
QMenu::item:selected { background: $ACCENT_SOFT; color: $ACCENT; }
QLabel#MatchScore { font-size: 34px; font-weight: 700; color: $ACCENT;
    background: $ACCENT_SOFT; border-radius: 14px; padding: 8px 18px; min-width: 90px; }
QLabel#GameScore { font-size: 22px; font-weight: 700; color: $ACCENT; padding: 4px 12px; }
QWidget#GameRow { background: $WINDOW; border-radius: 10px; }
QLabel#ScoreHeading { color: $TEXT_SEC; font-size: 11px; padding: 3px; }
QLabel#ScoreCell, QLabel#ScoreWinner, QLabel#ScoreCurrent {
    background: $WINDOW_ALT; border-radius: 5px; padding: 4px 7px; font-size: 14px; }
QLabel#ScoreWinner { background: $ACCENT_SOFT; color: $ACCENT; font-weight: 700; }
QLabel#ScoreCurrent { background: $LIVE_BG; color: $LIVE_TEXT; font-weight: 700; }
QLabel#MatchTime { font-size: 22px; font-weight: 700; color: $ACCENT; }
QLabel#SetScore { color: $TEXT_SEC; font-size: 13px; }
QLabel#DetailSet { color: $TEXT_SEC; font-size: 15px; }
QLabel#Meta { color: $TEXT_SEC; font-size: 12px; }
QLabel#EmptyText { color: $TEXT_SEC; font-size: 14px; }
QLabel#BadgeLive { background: $LIVE_BG; color: $LIVE_TEXT; border-radius: 9px;
    padding: 3px 10px; font-size: 11px; font-weight: 700; }
QLabel#BadgeFinal { background: $FINAL_BG; color: $FINAL_TEXT; border-radius: 9px;
    padding: 3px 10px; font-size: 11px; font-weight: 700; }
QLabel#BadgeStale { background: #FFF0D8; color: #9A5C00; border-radius: 9px;
    padding: 3px 10px; font-size: 11px; font-weight: 700; }
QLabel#SourceHealth { color: $TEXT_SEC; font-size: 11px; }
QLabel#BadgeTime { background: $ACCENT_SOFT; color: $ACCENT; border-radius: 9px;
    padding: 3px 10px; font-size: 12px; font-weight: 700; }
QLabel#AccentText { color: $ACCENT; }
QFrame#Card { background: $CARD; border: 1px solid $BORDER; border-radius: 16px; }
QFrame#Card:hover { background: $CARD_HOVER; border: 1px solid $ACCENT; }
QPushButton[nav="true"] { border: none; background: transparent; color: $TEXT;
    text-align: left; padding: 11px 14px; border-radius: 10px; font-size: 14px; }
QPushButton[nav="true"]:hover { background: $HOVER; }
QPushButton[nav="true"]:checked { background: $ACCENT_SOFT; color: $ACCENT; font-weight: 600; }
QPushButton[nav="true"][league="true"] { font-size: 13px; color: $TEXT_SEC; padding: 7px 14px; }
QPushButton[nav="true"][league="true"]:checked { color: $ACCENT; }
QPushButton#IconButton { border: none; background: transparent; border-radius: 8px;
    font-size: 16px; color: $TEXT_SEC; padding: 6px 8px; }
QPushButton#IconButton:hover { background: $HOVER; }
QPushButton#StarButton { border: none; background: transparent; font-size: 17px;
    color: $TEXT_SEC; padding: 2px; }
QPushButton#StarButton:hover { background: $HOVER; border-radius: 6px; }
QPushButton#StarButton[favorite="true"] { color: $ACCENT; }
QPushButton#BackButton { border: none; background: transparent; color: $ACCENT;
    font-size: 14px; padding: 6px 10px; border-radius: 8px; text-align: left; }
QPushButton#BackButton:hover { background: $ACCENT_SOFT; }
QLineEdit#SearchBox { background: $INPUT; border: 1px solid $BORDER; border-radius: 8px;
    padding: 7px 12px; font-size: 13px; color: $TEXT;
    selection-background-color: $ACCENT; selection-color: #FFFFFF; }
QLineEdit#SearchBox:focus { border: 1px solid $ACCENT; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $BORDER; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $TEXT_SEC; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: $BORDER; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
"""


class ThemeManager(QObject):
    changed = Signal()
    MODES = ["light", "dark", "system"]
    MODE_LABELS = {"light": "☀️ 浅色", "dark": "🌙 深色", "system": "🖥️ 跟随系统"}

    def __init__(self, settings: SettingsStore):
        super().__init__()
        self._settings = settings
        self.mode = settings.theme if settings.theme in self.MODES else "system"
        self._dark = False

    def is_dark(self) -> bool:
        return self._dark

    def colors(self) -> dict:
        return DARK if self._dark else LIGHT

    def mode_label(self) -> str:
        return self.MODE_LABELS[self.mode]

    def cycle(self) -> None:
        idx = self.MODES.index(self.mode)
        self.mode = self.MODES[(idx + 1) % len(self.MODES)]
        self._settings.set_theme(self.mode)
        self.apply()
        self.changed.emit()

    def apply(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        self._dark = self._resolve_dark()
        colors = self.colors()
        app.setPalette(_build_palette(colors))
        app.setStyleSheet(_build_stylesheet(colors))

    def follow_system(self) -> None:
        if self.mode == "system":
            self.apply()

    def _resolve_dark(self) -> bool:
        if self.mode != "system":
            return self.mode == "dark"
        hints = QApplication.styleHints()
        return hints.colorScheme() == Qt.ColorScheme.Dark


def _build_stylesheet(colors: dict) -> str:
    qss_colors = {k: v.name() if isinstance(v, QColor) else v for k, v in colors.items()}
    return Template(QSS).safe_substitute(qss_colors)


def _build_palette(colors: dict) -> QPalette:
    p = QPalette()
    window = QColor(colors["WINDOW"])
    card = QColor(colors["CARD"])
    input_bg = QColor(colors["INPUT"])
    text = QColor(colors["TEXT"])
    secondary = QColor(colors["TEXT_SEC"])
    accent = QColor(colors["ACCENT"])
    p.setColor(QPalette.ColorRole.Window, window)
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, input_bg)
    p.setColor(QPalette.ColorRole.AlternateBase, card)
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, card)
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.Highlight, accent)
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.Link, accent)
    p.setColor(QPalette.ColorRole.ToolTipBase, card)
    p.setColor(QPalette.ColorRole.ToolTipText, text)
    p.setColor(QPalette.ColorRole.PlaceholderText, secondary)
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        p.setColor(QPalette.ColorGroup.Disabled, role, secondary)
    return p
