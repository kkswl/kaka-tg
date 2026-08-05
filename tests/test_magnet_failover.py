import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[1] / "plugins.v2" / "tgsearch115" / "magnet_failover.py"
spec = importlib.util.spec_from_file_location("tgsearch115_magnet_failover", MODULE_PATH)
magnet_failover = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = magnet_failover
spec.loader.exec_module(magnet_failover)


def candidate(char):
    return SimpleNamespace(
        page_url="magnet:?xt=urn:btih:" + char * 40,
        title=f"candidate-{char}",
        _tg115_source="site",
    )


class MagnetFailoverTest(unittest.TestCase):
    def queue(self, count=3, max_attempts=5):
        return magnet_failover.build_magnet_queue(
            "movie:1:2025", "subscribe:1:movie:1", [candidate(str(i)) for i in range(count)],
            max_attempts=max_attempts,
            now=datetime(2026, 8, 5, tzinfo=timezone.utc),
            timeout_hours=12,
        )

    def test_cancelled_advances_to_next_candidate(self):
        queue = self.queue()
        self.assertEqual(magnet_failover.SUBMIT_NEXT, magnet_failover.advance_magnet_candidate(queue, "failed"))
        self.assertEqual(0, queue.current_index)
        self.assertEqual(magnet_failover.SUBMIT_NEXT, magnet_failover.advance_magnet_candidate(queue, "cancelled"))
        self.assertEqual(1, queue.current_index)
        self.assertEqual(2, len(queue.attempted_btih))

    def test_active_status_waits(self):
        queue = self.queue()
        self.assertEqual(magnet_failover.SUBMIT_NEXT, magnet_failover.advance_magnet_candidate(queue, "failed"))
        self.assertEqual(magnet_failover.WAIT, magnet_failover.advance_magnet_candidate(queue, "downloading"))
        self.assertEqual(0, queue.current_index)

    def test_unknown_requires_reconciliation(self):
        queue = self.queue()
        self.assertEqual(magnet_failover.SUBMIT_NEXT, magnet_failover.advance_magnet_candidate(queue, "failed"))
        self.assertEqual(magnet_failover.RECONCILE, magnet_failover.advance_magnet_candidate(queue, "unknown"))
        self.assertEqual(1, len(queue.attempted_btih))

    def test_completed_stops_and_releases_owner(self):
        queue = self.queue()
        self.assertEqual(magnet_failover.SUBMIT_NEXT, magnet_failover.advance_magnet_candidate(queue, "failed"))
        self.assertEqual(magnet_failover.COMPLETE, magnet_failover.advance_magnet_candidate(queue, "completed"))
        self.assertEqual("none", queue.owner)

    def test_duplicate_btih_is_removed_and_max_attempts_falls_back(self):
        queue = self.queue(count=3, max_attempts=2)
        queue.candidates.append(dict(queue.candidates[0]))
        queue._deduplicate()
        self.assertEqual(3, len(queue.candidates))
        self.assertEqual(magnet_failover.SUBMIT_NEXT, magnet_failover.advance_magnet_candidate(queue, "failed"))
        self.assertEqual(magnet_failover.SUBMIT_NEXT, magnet_failover.advance_magnet_candidate(queue, "failed"))
        self.assertEqual(magnet_failover.FALLBACK_TO_MOVIEPILOT, magnet_failover.advance_magnet_candidate(queue, "failed"))

    def test_expired_queue_falls_back_without_switching(self):
        queue = self.queue()
        queue.expires_at = datetime(2026, 8, 5, tzinfo=timezone.utc)
        self.assertEqual(
            magnet_failover.FALLBACK_TO_MOVIEPILOT,
            magnet_failover.advance_magnet_candidate(queue, "failed", datetime(2026, 8, 5, 0, 1, tzinfo=timezone.utc)),
        )

    def test_restart_dump_preserves_attempt_history(self):
        queue = self.queue()
        magnet_failover.advance_magnet_candidate(queue, "failed")
        restored = magnet_failover.restore_magnet_queue(queue.dump())
        self.assertEqual(0, restored.current_index)
        self.assertEqual(1, len(restored.attempted_btih))
        self.assertEqual("tg115", restored.owner)
        self.assertEqual(magnet_failover.SUBMIT_NEXT, magnet_failover.advance_magnet_candidate(restored, "cancelled"))
        self.assertEqual(1, restored.current_index)

    def test_waiting_organize_full_season_blocks_missing_episode(self):
        full_season = candidate("a")
        full_season._tg115_season = 1
        full_season._tg115_declared_episodes = list(range(1, 41))
        full_season._tg115_is_complete = True
        queue = magnet_failover.build_magnet_queue("tv:1:S1", "1:tv:1:S1", [full_season])
        magnet_failover.advance_magnet_candidate(queue, "failed")
        queue.mark("waiting_organize")
        self.assertEqual(set(), magnet_failover.effective_missing_episodes({26}, queue))
        queue.mark("failed")
        self.assertEqual({26}, magnet_failover.effective_missing_episodes({26}, queue))


if __name__ == "__main__":
    unittest.main()
