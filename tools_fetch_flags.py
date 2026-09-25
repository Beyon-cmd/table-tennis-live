"""Build-time only: bundle public association flags used by WTT."""
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import httpx

BASE = "https://documentstore.ittf.com/websitefiles/assets/"

if __name__ == "__main__":
    js = (Path(__file__).parent.parent.parent / "work/wtt_main.js").read_text(encoding="utf-8")
    flags = dict(re.findall(r'countryCode:"([A-Z]{3})",[^{}]*?flag:"([^"]+)"', js))
    directory = Path(__file__).parent / "assets/flags"
    directory.mkdir(parents=True, exist_ok=True)
    def fetch(item):
        code, path = item
        target = directory / (code + ".png")
        if target.exists():
            return True
        try:
            response = httpx.get(BASE + path, timeout=15, follow_redirects=True)
            response.raise_for_status()
            from PySide6.QtGui import QImage
            image = QImage.fromData(response.content)
            if image.isNull():
                return False
            return image.save(str(target), "PNG")
        except Exception:
            print("Unavailable:", code)
            return False
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(fetch, flags.items()))
    print("Bundled", sum(results), "of", len(flags), "official flags")
