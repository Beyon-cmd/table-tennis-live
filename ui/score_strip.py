"""共享逐局记分板：同一列对应同一局，上下对应双方。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget


class ScoreStrip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 6, 0, 6)
        self.grid.setSpacing(4)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_scores(self, sets, current=None):
        for col in range(self.grid.columnCount()):
            self.grid.setColumnStretch(col, 0)
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        pairs = list(sets)
        if current is not None:
            pairs.append(current)
        self.setVisible(bool(pairs))
        if not pairs:
            return
        for row, text in enumerate(("左方", "右方"), 1):
            label = QLabel(text)
            label.setObjectName("ScoreHeading")
            self.grid.addWidget(label, row, 0)
        for col, (a, b) in enumerate(pairs, 1):
            live = current is not None and col == len(pairs)
            heading = QLabel("本局" if live else f"第 {col} 局")
            heading.setObjectName("ScoreHeading")
            heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid.addWidget(heading, 0, col)
            for row, points in enumerate((a, b), 1):
                cell = QLabel(str(points))
                winner = (row == 1 and a > b) or (row == 2 and b > a)
                cell.setObjectName("ScoreCurrent" if live else "ScoreWinner" if winner else "ScoreCell")
                cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cell.setMinimumWidth(38)
                self.grid.addWidget(cell, row, col)
        self.grid.setColumnStretch(len(pairs) + 1, 1)
