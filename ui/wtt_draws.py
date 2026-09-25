"""Event-based draw tab: official connections, draggable canvas, safe async loads."""
from datetime import datetime
import threading
from PySide6.QtCore import Qt, Signal, QTimer, QRectF
from PySide6.QtGui import QColor, QPen, QPainter, QPainterPath, QFont, QPixmap, QFontMetrics
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsItem, QDialog)
from ui.modern_select import ModernSelect
from data_sources.wtt_draws import PROJECTS, fetch_events, fetch_draws
from ui.flags import flag_path
from ui.score_strip import ScoreStrip
from ui.player_link import PlayerLink
from data_sources.player_profiles import PlayerRequest

STAGES = {"MAIN": "正赛", "PREL": "资格赛", "PRE": "资格赛", "FNL": "正赛", "BRN": "铜牌赛"}
CARD_W, CARD_H, GAP_X, STEP_Y = 300, 116, 68, 148


class DrawCard(QGraphicsRectItem):
    def __init__(self, match, colors, callback, player_callback=None):
        super().__init__(0, 0, CARD_W, CARD_H)
        self.match, self.colors, self.callback = match, colors, callback
        self.player_callback = player_callback
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("\n".join(p["raw"] for p in match["players"]) + "\n" + match["result"] + "\n点击选手名看资料；点击卡片其他位置看小比分")
        self.hovered = False

    def hoverEnterEvent(self, event):
        self.hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self.hovered = False
        self.update()

    def mousePressEvent(self, event):
        self._pressed = event.screenPos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and (event.screenPos() - getattr(self, "_pressed", event.screenPos())).manhattanLength() < 8:
            x, y = event.pos().x(), event.pos().y()
            index = int((y - 12) // 33)
            if self.player_callback and 14 <= x <= 261 and index in (0, 1) and 12 + index*33 <= y < 39 + index*33:
                player = self.match["players"][index]
                if player["name"] not in ("轮空", "待定"):
                    self.player_callback(player)
                else:
                    self.callback(self.match)
            else:
                self.callback(self.match)
        super().mouseReleaseEvent(event)

    def paint(self, painter, option, widget=None):
        c, m = self.colors, self.match
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(c["ACCENT"] if self.hovered else c["BORDER"]), 1.4))
        painter.setBrush(QColor(c["CARD_HOVER"] if self.hovered else c["CARD"]))
        painter.drawRoundedRect(self.rect().adjusted(1,1,-1,-1), 13, 13)
        for index, player in enumerate(m["players"]):
            y = 12 + index * 33
            path = flag_path(player["country"])
            if path:
                painter.drawPixmap(14, y+5, 23, 15, QPixmap(str(path)))
            font = QFont("Microsoft YaHei UI", 10)
            font.setBold(player["winner"])
            painter.setFont(font)
            painter.setPen(QColor(c["ACCENT"] if player["winner"] else c["TEXT"]))
            name = player["name"] + (f" [{player['seed']}]" if player["seed"] else "")
            painter.drawText(QRectF(44,y,216,27), Qt.AlignmentFlag.AlignVCenter, QFontMetrics(font).elidedText(name, Qt.TextElideMode.ElideRight, 213))
            painter.drawText(QRectF(263,y,24,27), Qt.AlignmentFlag.AlignCenter, player["score"])
        painter.setPen(QColor(c["BORDER"]))
        painter.drawLine(14, 81, CARD_W-14, 81)
        painter.setFont(QFont("Microsoft YaHei UI", 8))
        painter.setPen(QColor(c["TEXT_SEC"]))
        caption = "轮空晋级" if m["bye"] else "已结束 · 点击查看小比分" if any(p["winner"] for p in m["players"]) else (m["date"] + "  " + m["time"]).strip() or "等待官方安排"
        painter.drawText(QRectF(14,86,CARD_W-28,23), Qt.AlignmentFlag.AlignVCenter, caption)


class DrawCanvas(QGraphicsView):
    def __init__(self, theme, callback, player_callback=None, parent=None):
        super().__init__(parent)
        self.theme, self.callback, self.player_callback = theme, callback, player_callback
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setObjectName("DrawCanvas")
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        corner = QWidget()
        corner.setObjectName("ScrollCorner")
        self.setCornerWidget(corner)
        self._zoom = 1.0
        self.rounds = []

    @property
    def zoom(self):
        return self._zoom

    def set_zoom(self, value):
        value = max(0.35,min(2.5,round(value,2)))
        if value == self._zoom:
            return
        self.scale(value/self._zoom,value/self._zoom)
        self._zoom = value
        self.zoom_changed(value)

    def zoom_changed(self,value):
        pass

    def fit_width(self):
        rect = self.scene().sceneRect()
        if rect.width() > 0:
            self.set_zoom((self.viewport().width()-18)/rect.width())

    def wheelEvent(self,event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                self.set_zoom(self._zoom*(1.12 if delta > 0 else 1/1.12))
                event.accept()
                return
        super().wheelEvent(event)

    def display(self, rounds, preserve=False):
        old_x, old_y = self.horizontalScrollBar().value(), self.verticalScrollBar().value()
        self.rounds = rounds
        scene = self.scene()
        scene.clear()
        colors = self.theme.colors()
        self.setBackgroundBrush(QColor(colors["WINDOW"]))
        positions = {}
        for col, group in enumerate(rounds):
            x = 20 + col * (CARD_W + GAP_X)
            title = scene.addText(group["title"], QFont("Microsoft YaHei UI", 12, QFont.Weight.Bold))
            title.setDefaultTextColor(QColor(colors["TEXT"]))
            title.setPos(x, 8)
            floor = 60
            for row, match in enumerate(group["matches"]):
                parents = [positions[p["previous"]] for p in match["players"] if p["previous"] in positions]
                y = sum(p[1] for p in parents)/len(parents) if parents else 60 + row * STEP_Y
                y = max(floor, y)
                floor = y + STEP_Y
                positions[match["id"]] = (x,y)
                item = DrawCard(match, colors, self.callback, self.player_callback)
                item.setPos(x,y)
                scene.addItem(item)
                # Only explicit official predecessor identifiers create edges.
                for px, py in parents:
                    path = QPainterPath()
                    path.moveTo(px+CARD_W,py+CARD_H/2)
                    path.cubicTo(px+CARD_W+GAP_X/2,py+CARD_H/2,x-GAP_X/2,y+CARD_H/2,x,y+CARD_H/2)
                    edge = scene.addPath(path,QPen(QColor(colors["BORDER"]),2))
                    edge.setZValue(-1)
        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-12,-8,28,28))
        self.horizontalScrollBar().setValue(old_x if preserve else 0)
        self.verticalScrollBar().setValue(old_y if preserve else 0)


class WTTDrawsPage(QWidget):
    ready = Signal(object, object, str)
    player_clicked = Signal(object)

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._closed = threading.Event()
        self._busy = False
        self._events = []
        self._data = {}
        self._loaded_key = None
        self._display_key = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24,16,24,20)
        title = QLabel("赛事签表")
        title.setObjectName("HeroTitle")
        layout.addWidget(title)
        caption = QLabel("官方晋级路线 · 拖动或滚动浏览 · Ctrl＋滚轮缩放 · 点击卡片查看小比分")
        caption.setObjectName("Meta")
        caption.setWordWrap(True)
        layout.addWidget(caption)
        row = QHBoxLayout()
        self.event_combo = ModernSelect("选择赛事", searchable=True)
        self.event_combo.setMinimumWidth(240)
        self.project = ModernSelect("选择项目")
        for title, code in PROJECTS.items():
            self.project.addItem(title,code)
        self.stage = ModernSelect("选择阶段")
        self.refresh_button = QPushButton("刷新签表")
        self.refresh_button.setObjectName("RankingButton")
        row.addWidget(self.event_combo,1)
        row.addWidget(self.project)
        row.addWidget(self.stage)
        row.addWidget(self.refresh_button)
        layout.addLayout(row)
        self.status = QLabel("选择赛事后加载官方签表")
        self.status.setObjectName("Meta")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        zoom_row = QHBoxLayout()
        zoom_label = QLabel("签表缩放")
        zoom_label.setObjectName("Meta")
        zoom_row.addWidget(zoom_label)
        zoom_row.addStretch()
        self.zoom_out = QPushButton("－")
        self.zoom_in = QPushButton("＋")
        self.zoom_reset = QPushButton("100%")
        self.zoom_fit = QPushButton("适应宽度")
        for button in (self.zoom_out,self.zoom_reset,self.zoom_in,self.zoom_fit):
            button.setObjectName("ZoomButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            zoom_row.addWidget(button)
        layout.addLayout(zoom_row)
        self.canvas = DrawCanvas(theme, self.open_match, self._open_player)
        layout.addWidget(self.canvas,1)
        self.canvas.zoom_changed = lambda value: self.zoom_reset.setText(f"{round(value*100)}%")
        self.zoom_out.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.zoom/1.2))
        self.zoom_in.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.zoom*1.2))
        self.zoom_reset.clicked.connect(lambda: self.canvas.set_zoom(1.0))
        self.zoom_fit.clicked.connect(self.canvas.fit_width)
        self.event_combo.currentIndexChanged.connect(self.selection_changed)
        self.project.currentIndexChanged.connect(self.selection_changed)
        self.stage.currentIndexChanged.connect(self.render)
        self.refresh_button.clicked.connect(self.refresh)
        self.ready.connect(self.complete)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(30000)
        self.timer.timeout.connect(self.refresh)
        theme.changed.connect(self.retheme)

    def showEvent(self,event):
        super().showEvent(event)
        self.refresh()

    def hideEvent(self,event):
        self.timer.stop()
        super().hideEvent(event)

    def key(self):
        return (self.event_combo.currentData(),self.project.currentData())

    def selection_changed(self, *_):
        self._data = {}
        self._loaded_key = None
        self._display_key = None
        self.stage.clear()
        self.canvas.display([])
        self.refresh()

    def refresh(self):
        if self._closed.is_set() or self._busy:
            return
        self.timer.stop()
        self._busy = True
        self.refresh_button.setEnabled(False)
        key = self.key() if self._events else None
        self.status.setText("正在读取官方签表…" if key else "正在获取近期 WTT 主级别赛事…")
        def work():
            try:
                data = fetch_draws(*key) if key else fetch_events()
                error = ""
            except Exception as exc:
                data, error = None, str(exc)
            if not self._closed.is_set():
                try:
                    self.ready.emit(key,data,error)
                except RuntimeError:
                    pass
        threading.Thread(target=work,daemon=True).start()

    def complete(self,key,data,error):
        if self._closed.is_set():
            return
        self._busy = False
        self.refresh_button.setEnabled(True)
        if key is not None and key != self.key():
            self.refresh()
            return
        if error:
            self.status.setText("暂时无法更新 · 保留当前签表，稍后自动重试" if self._data else "官方签表暂时无法获取，请点击刷新重试")
            self.status.setToolTip(error)
        elif key is None:
            self._events = data
            self.event_combo.blockSignals(True)
            self.event_combo.clear()
            for event in data:
                self.event_combo.addItem(event["name"],event["id"])
            self.event_combo.blockSignals(False)
            if data:
                self.refresh()
                return
            self.status.setText("近期暂无可选赛事")
        else:
            changed = self._data != data or self._loaded_key != key
            self._loaded_key, self._data = key, data
            self.status.setToolTip("")
            self.status.setText(f"{datetime.now():%H:%M:%S} 已核对官方数据 · 每 30 秒检查 · 时间为赛事当地时间" if data else "此项目签表尚未发布或未设置 · 可切换其他项目")
            if changed:
                selected = self.stage.currentData()
                self.stage.blockSignals(True)
                self.stage.clear()
                for stage in data:
                    self.stage.addItem(STAGES.get(stage,stage),stage)
                index = self.stage.findData(selected)
                self.stage.setCurrentIndex(max(index,0))
                self.stage.blockSignals(False)
                self.render()
        if self.isVisible():
            self.timer.start()

    def render(self,*_):
        key = (self.key(),self.stage.currentData())
        self.canvas.display(self._data.get(self.stage.currentData(),[]),preserve=key == self._display_key)
        self._display_key = key

    def retheme(self):
        self.canvas.display(self.canvas.rounds,preserve=True)

    def open_match(self,match):
        dialog = QDialog(self)
        dialog.setWindowTitle("签表比赛详情")
        dialog.resize(580,300)
        layout = QVBoxLayout(dialog)
        for player in match["players"]:
            label = PlayerLink(f"{player['name']}  ·  {player['country']}    {player['score']}")
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setObjectName("SectionTitle")
            label.setEnabled(player["name"] not in ("轮空", "待定"))
            label.clicked.connect(lambda p=player: self._open_player(p))
            layout.addWidget(label)
        strip = ScoreStrip()
        strip.set_scores(match["sets"],None)
        layout.addWidget(strip)
        note = QLabel("轮空晋级，不计实际比赛比分" if match["bye"] else "官方尚未提供逐局比分" if not match["sets"] else "上行为第一位选手，下行为第二位选手")
        note.setObjectName("Meta")
        layout.addWidget(note)
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_button = QPushButton("关闭")
        close_button.setObjectName("RankingButton")
        close_button.setMinimumWidth(92)
        close_button.clicked.connect(dialog.accept)
        close_row.addWidget(close_button)
        layout.addLayout(close_row)
        dialog.exec()

    def _open_player(self, player):
        self.player_clicked.emit(PlayerRequest(player["name"], player["raw"], player["country"], player.get("player_id", "")))

    def shutdown(self):
        self._closed.set()
        self.timer.stop()
