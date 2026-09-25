"""Bundled official WTT association flags, including TPE and neutral entries."""
import re
import html
from pathlib import Path
from PySide6.QtCore import QUrl

FLAGS = Path(__file__).resolve().parent.parent / "assets/flags"


def flag_path(code):
    if not re.fullmatch(r"[A-Z]{3}", code or ""):
        return None
    path = FLAGS / (code + ".png")
    return path if path.is_file() else None


def player_html(name):
    match = re.search(r"\s*\(([A-Z]{3})\)$", name)
    if match:
        path = flag_path(match[1])
        if path:
            url = html.escape(QUrl.fromLocalFile(str(path)).toString(), quote=True)
            return f'<img src="{url}" width="27" height="18"> &nbsp;{html.escape(name[:match.start()])}'
    return html.escape(name)
