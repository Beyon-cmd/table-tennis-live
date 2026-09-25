"""得分差走势图：实线为连续观察，虚线表示两次观察之间有缺失回合。"""
from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from services.score_trend import TrendPoint


class ScoreTrendWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(230)
        self.setMouseTracking(True)
        self._points: list[TrendPoint] = []
        self._hit_targets: list[tuple[QPoint, TrendPoint]] = []

    def set_points(self, points: list[TrendPoint]) -> None:
        self._points = points
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fg = self.palette().color(self.foregroundRole())
        muted = QColor(fg)
        muted.setAlpha(105)
        left, right, top, bottom = 46, self.width() - 16, 18, self.height() - 43
        if right <= left or bottom <= top:
            return
        if not self._points:
            painter.setPen(muted)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无可绘制的局分样本")
            return

        grouped: dict[int, list[TrendPoint]] = defaultdict(list)
        for point in self._points:
            grouped[point.set_number].append(point)
        numbers = sorted(grouped)
        max_diff = max(5, max(abs(p.difference) for p in self._points))
        max_diff = ((max_diff + 4) // 5) * 5
        total = sum(max(p.progress for p in grouped[n]) + 4 for n in numbers)
        width, height = right - left, bottom - top

        def x_at(progress: int) -> int:
            return left + round(width * progress / max(1, total))

        def y_at(difference: int) -> int:
            return top + round(height * (max_diff - difference) / (2 * max_diff))

        painter.setPen(QPen(muted, 1, Qt.PenStyle.DotLine))
        for diff in (-max_diff, 0, max_diff):
            y = y_at(diff)
            painter.drawLine(left, y, right, y)
            painter.drawText(2, y - 7, left - 7, 14,
                             Qt.AlignmentFlag.AlignRight, f"{diff:+d}" if diff else "0")

        offset = 0
        self._hit_targets = []
        for number in numbers:
            rows = sorted(grouped[number], key=lambda p: p.progress)
            start_x = x_at(offset)
            end_progress = max(p.progress for p in rows)
            end_x = x_at(offset + end_progress)
            painter.setPen(QPen(muted, 1))
            painter.drawText(start_x, bottom + 6, max(30, end_x - start_x), 16,
                             Qt.AlignmentFlag.AlignCenter, f"第{number}局")
            if number != numbers[0]:
                painter.setPen(QPen(muted, 1, Qt.PenStyle.DashLine))
                painter.drawLine(start_x, top, start_x, bottom)
            previous = None
            for point in rows:
                position = QPoint(x_at(offset + point.progress), y_at(point.difference))
                color = QColor("#2563EB" if point.difference >= 0 else "#E05B50")
                if previous is not None:
                    old_position, old_point = previous
                    style = (Qt.PenStyle.SolidLine if point.progress - old_point.progress == 1
                             else Qt.PenStyle.DashLine)
                    painter.setPen(QPen(color, 2, style))
                    painter.drawLine(old_position, position)
                painter.setPen(QPen(color, 2))
                painter.setBrush(color if not point.final else self.palette().color(self.backgroundRole()))
                painter.drawEllipse(position, 4, 4)
                if (point.official_events or point.game_point_player is not None
                        or point.match_point_player is not None or point.streak_count >= 3):
                    painter.setPen(QPen(QColor("#E89B18"), 2))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawEllipse(position, 7, 7)
                self._hit_targets.append((position, point))
                previous = (position, point)
            offset += end_progress + 4

        painter.setPen(muted)
        painter.drawText(left, bottom + 24, width, 16, Qt.AlignmentFlag.AlignCenter,
                         "比赛进程 · 每局累计得分（虚线表示漏采样）")

    def mouseMoveEvent(self, event) -> None:
        near = min(self._hit_targets,
                   key=lambda item: (item[0] - event.position().toPoint()).manhattanLength(),
                   default=None)
        if near is None or (near[0] - event.position().toPoint()).manhattanLength() > 14:
            self.setToolTip("")
            return
        point = near[1]
        notes = [f"第 {point.set_number} 局  {point.score_a}:{point.score_b}",
                 f"分差 {point.difference:+d}" if point.difference else "双方平分"]
        if point.final:
            notes.append("局末比分")
        if "timeout" in point.official_events:
            notes.append("官方暂停记录")
        if point.game_point_player is not None:
            notes.append("局点")
        if point.match_point_player is not None or "match_point" in point.official_events:
            notes.append("赛点")
        if point.streak_count >= 3:
            notes.append(f"{'左方' if point.streak_player == 0 else '右方'}连续 {point.streak_count} 分（连续采样）")
        self.setToolTip(" · ".join(notes))
