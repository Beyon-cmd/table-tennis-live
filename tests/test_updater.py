import threading
import time
import unittest
from datetime import datetime
from PySide6.QtCore import QCoreApplication
from models import Match
from services.updater import _UpdaterWorker


class UpdaterTests(unittest.TestCase):
    def test_outage_marks_cached_score_stale_and_recovery_clears_it(self):
        class Source:
            name = "WTT"
            calls = 0

            def get_matches(self):
                self.calls += 1
                if self.calls == 2:
                    raise RuntimeError("offline")
                return [Match("m1", self.name, "Test", "live", datetime(2026, 9, 19),
                              "A", "B", score_a=self.calls)]

        source = Source()
        app = QCoreApplication.instance() or QCoreApplication([])
        worker = _UpdaterWorker([source], live_interval=0.05)
        seen = []
        statuses = []
        worker.changed.connect(lambda matches: seen.extend((m.score_a, m.data_stale) for m in matches))
        worker.source_status.connect(lambda name, checked, error: statuses.append((checked, error)))
        worker.start()
        try:
            deadline = time.monotonic() + 3
            while (not seen or seen[-1] != (3, False)) and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.02)
            self.assertGreaterEqual(source.calls, 3)
            self.assertIn((1, True), seen)
            self.assertIn((3, False), seen)
            self.assertTrue(any(error == "offline" for _, error in statuses))
            self.assertEqual(statuses[-1][1], "")
            self.assertFalse(worker._snapshot["m1"].data_stale)
        finally:
            worker.stop()

    def test_slow_source_does_not_block_fast_source(self):
        release = threading.Event()
        class Source:
            def __init__(self, name, slow=False):
                self.name, self.slow, self.calls = name, slow, 0
            def get_matches(self):
                if self.slow:
                    release.wait(3)
                self.calls += 1
                if self.calls == 2:
                    raise RuntimeError("temporary outage")
                return [Match(self.name, self.name, "Test", "live", datetime(2026,9,19), "A", "B")]
        fast, slow = Source("fast"), Source("slow", True)
        worker = _UpdaterWorker([slow, fast], live_interval=0.1)
        worker.start()
        try:
            deadline = time.monotonic() + 2
            while fast.calls < 2 and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertGreaterEqual(fast.calls, 2)
            self.assertEqual(slow.calls, 0)
            self.assertIn("fast", worker._snapshot)
        finally:
            release.set()
            worker.stop()
