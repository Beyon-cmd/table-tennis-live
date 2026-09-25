"""从透明 PNG 生成包含任务栏到高分屏尺寸的 Windows ICO。"""
from __future__ import annotations

import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "assets" / "icon-source.png"
DESTINATION = ROOT / "assets" / "icon.ico"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def png_bytes(image: QImage) -> bytes:
    payload = QBuffer()
    payload.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(payload, "PNG"):
        raise RuntimeError("无法编码图标 PNG")
    return bytes(payload.data())


def build_icon() -> None:
    original = QImage(str(SOURCE)).convertToFormat(QImage.Format.Format_ARGB32)
    if original.isNull() or not original.hasAlphaChannel():
        raise ValueError("图标原图必须是带透明通道的 PNG")
    edge = max(original.width(), original.height())
    square = QImage(edge, edge, QImage.Format.Format_ARGB32)
    square.fill(Qt.GlobalColor.transparent)
    painter = QPainter(square)
    painter.drawImage((edge - original.width()) // 2, (edge - original.height()) // 2, original)
    painter.end()
    images = [png_bytes(square.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation))
              for size in SIZES]
    offset = 6 + 16 * len(images)
    entries = []
    for size, payload in zip(SIZES, images):
        entries.append(struct.pack("<BBBBHHII", size if size < 256 else 0,
                                   size if size < 256 else 0, 0, 0, 1, 32,
                                   len(payload), offset))
        offset += len(payload)
    DESTINATION.write_bytes(struct.pack("<HHH", 0, 1, len(images))
                            + b"".join(entries) + b"".join(images))
    print(f"已生成 {DESTINATION}：{', '.join(map(str, SIZES))} px")


if __name__ == "__main__":
    build_icon()
