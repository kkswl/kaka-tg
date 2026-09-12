import importlib.util
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[1] / "plugins.v2" / "tgsearch115" / "cms_tasks.py"
spec = importlib.util.spec_from_file_location("tgsearch115_cms_tasks", MODULE_PATH)
cms_tasks = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cms_tasks
spec.loader.exec_module(cms_tasks)


def magnet(char="a"):
    return "magnet:?xt=urn:btih:" + char * 40


class CmsTaskLedgerTest(unittest.TestCase):
    def test_clear_requires_explicit_confirmation(self):
        self.assertFalse(cms_tasks.has_explicit_clear_confirmation(None))
        self.assertFalse(cms_tasks.has_explicit_clear_confirmation({}))
        self.assertFalse(cms_tasks.has_explicit_clear_confirmation({"confirm": "true"}))
        self.assertTrue(cms_tasks.has_explicit_clear_confirmation({"confirm": True}))

    def test_clear_records_refuses_to_drop_active_task_tracking(self):
        ledger = cms_tasks.CmsTaskLedger()
        ledger.add("magnet:?xt=urn:btih:" + "a" * 40, "active")

        cleared, active = ledger.clear_if_idle()

        self.assertEqual((0, 1), (cleared, active))
        self.assertEqual(1, len(ledger.dump_records()))

    def test_clear_records_removes_terminal_history(self):
        ledger = cms_tasks.CmsTaskLedger()
        magnet = "magnet:?xt=urn:btih:" + "b" * 40
        ledger.add(magnet, "done")
        ledger.update("b" * 40, "completed")

        cleared, active = ledger.clear_if_idle()

        self.assertEqual((1, 0), (cleared, active))
        self.assertEqual([], ledger.dump_records())

    def test_active_btih_is_deduplicated_across_reload(self):
        now = datetime(2026, 7, 20, tzinfo=timezone.utc)
        ledger = cms_tasks.CmsTaskLedger(now=lambda: now)
        subscribe = SimpleNamespace(
            id=8, tmdbid=100, doubanid=None, type="MOVIE", season=None
        )
        first = ledger.add(magnet(), "示例电影", subscribe=subscribe)
        restored = cms_tasks.CmsTaskLedger(ledger.records, now=lambda: now)

        self.assertEqual(first["btih"], restored.active_by_btih("a" * 40)["btih"])
        self.assertNotIn("magnet", restored.public_records()[0])

    def test_reload_migrates_legacy_magnet_without_persisting_it(self):
        legacy = cms_tasks.CmsTaskLedger([{"btih": "a" * 40, "magnet": magnet(), "status": "downloading"}])
        self.assertNotIn("magnet", legacy.dump_records()[0])
        self.assertNotIn("magnet", legacy.public_records()[0])
        self.assertNotEqual("", legacy.public_records()[0]["source"])

    def test_btih_reservation_is_atomic(self):
        now = datetime(2026, 7, 20, tzinfo=timezone.utc)
        ledger = cms_tasks.CmsTaskLedger(now=lambda: now)

        first, first_created = ledger.reserve(magnet(), "示例电影")
        second, second_created = ledger.reserve(magnet(), "重复任务")

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertIs(first, second)
        self.assertEqual(1, len(ledger.records))

    def test_concurrent_same_subscription_has_one_active_record(self):
        ledger = cms_tasks.CmsTaskLedger()
        barrier = threading.Barrier(10)

        subscribe = SimpleNamespace(id=7, tmdbid=1, doubanid=None, type="MOVIE", season=None)

        def create():
            barrier.wait()
            return ledger.reserve("magnet:?xt=urn:btih:" + "f" * 40, title="movie", subscribe=subscribe)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create) for _ in range(10)]
            records = [future.result() for future in futures]

        self.assertEqual(1, sum(created for _record, created in records))
        self.assertEqual("f" * 40, ledger.active_by_subscription(7)["btih"])

    def test_cms_acceptance_does_not_complete_subscription(self):
        now = datetime(2026, 7, 20, tzinfo=timezone.utc)
        ledger = cms_tasks.CmsTaskLedger(now=lambda: now)
        ledger.add(magnet(), "示例电影", subscribe=SimpleNamespace(
            id=8, tmdbid=100, doubanid=None, type="MOVIE", season=None
        ))

        result = ledger.reconcile(
            timeout_hours=12,
            subscription_exists=lambda _sid: True,
            history_exists=lambda _record: False,
            restore_subscription=lambda _sid: self.fail("should not restore"),
        )

        self.assertEqual({"completed": 0, "failed": 0, "timed_out": 0}, result)
        self.assertEqual("downloading", ledger.records[0]["status"])

    def test_timeout_restores_subscription(self):
        now = [datetime(2026, 7, 20, tzinfo=timezone.utc)]
        ledger = cms_tasks.CmsTaskLedger(now=lambda: now[0])
        ledger.add(magnet(), "示例电影", subscribe=SimpleNamespace(
            id=8, tmdbid=100, doubanid=None, type="MOVIE", season=None
        ))
        now[0] += timedelta(hours=13)
        restored = []

        result = ledger.reconcile(
            timeout_hours=12,
            subscription_exists=lambda _sid: True,
            history_exists=lambda _record: False,
            restore_subscription=restored.append,
        )

        self.assertEqual(1, result["timed_out"])
        self.assertEqual([8], restored)
        self.assertEqual("timed_out", ledger.records[0]["status"])

    def test_moviepilot_history_marks_task_completed(self):
        now = datetime(2026, 7, 20, tzinfo=timezone.utc)
        ledger = cms_tasks.CmsTaskLedger(now=lambda: now)
        ledger.add(magnet(), "示例电影", subscribe=SimpleNamespace(
            id=8, tmdbid=100, doubanid=None, type="MOVIE", season=None
        ))

        result = ledger.reconcile(
            timeout_hours=12,
            subscription_exists=lambda _sid: True,
            history_exists=lambda _record: True,
            restore_subscription=lambda _sid: None,
        )

        self.assertEqual(1, result["completed"])
        self.assertEqual("completed", ledger.records[0]["status"])
        self.assertFalse(ledger.records[0]["completion_notified"])
        self.assertEqual("matched", ledger.records[0]["mp_history_match_status"])
        self.assertIn("订阅历史", ledger.records[0]["organize_wait_reason"])

    def test_pending_organize_records_history_diagnostic_without_completing(self):
        now = datetime(2026, 7, 20, tzinfo=timezone.utc)
        ledger = cms_tasks.CmsTaskLedger(now=lambda: now)
        record = ledger.add(magnet(), "示例电影", subscribe=SimpleNamespace(
            id=8, tmdbid=100, doubanid=None, type="MOVIE", season=None
        ))
        ledger.update(record["btih"], "pending_organize")
        result = ledger.reconcile(
            timeout_hours=12,
            subscription_exists=lambda _sid: True,
            history_exists=lambda _record: False,
            restore_subscription=lambda _sid: None,
        )
        self.assertEqual(0, result["completed"])
        self.assertEqual("not_found", record["mp_history_match_status"])
        self.assertTrue(record["mp_history_checked_at"])
        self.assertIn("等待 MoviePilot", record["organize_wait_reason"])

    def test_completed_record_is_not_reconciled_again(self):
        now = datetime(2026, 7, 20, tzinfo=timezone.utc)
        ledger = cms_tasks.CmsTaskLedger(now=lambda: now)
        record = ledger.add(magnet(), "示例电影", subscribe=SimpleNamespace(
            id=8, tmdbid=100, doubanid=None, type="MOVIE", season=None
        ))
        ledger.update(record["btih"], "completed", completion_notified=True)
        result = ledger.reconcile(
            timeout_hours=12,
            subscription_exists=lambda _sid: self.fail("completed task was reconciled"),
            history_exists=lambda _record: self.fail("completed task checked history"),
            restore_subscription=lambda _sid: self.fail("completed task restored"),
        )
        self.assertEqual({"completed": 0, "failed": 0, "timed_out": 0}, result)
        self.assertTrue(ledger.records[0]["completion_notified"])

    def test_transfer_complete_matches_unique_pending_movie(self):
        ledger = cms_tasks.CmsTaskLedger()
        record = ledger.add(magnet(), "示例电影", subscribe=SimpleNamespace(
            id=8, tmdbid=100, doubanid=None, type="MOVIE", season=None
        ))
        ledger.update(record["btih"], "pending_organize")

        matched = ledger.match_transfer_complete(tmdb_id=100, media_type="电影")

        self.assertEqual(record["btih"], matched["btih"])

    def test_transfer_complete_requires_matching_tv_season(self):
        ledger = cms_tasks.CmsTaskLedger()
        record = ledger.add(magnet(), "示例剧集", subscribe=SimpleNamespace(
            id=8, tmdbid=100, doubanid=None, type="TV", season=2
        ))
        ledger.update(record["btih"], "pending_organize")

        self.assertIsNone(ledger.match_transfer_complete(tmdb_id=100, media_type="电视剧"))
        self.assertIsNone(ledger.match_transfer_complete(tmdb_id=100, media_type="TV", season=1))
        self.assertEqual(
            record["btih"],
            ledger.match_transfer_complete(tmdb_id=100, media_type="TV", season=2)["btih"],
        )

    def test_transfer_complete_reports_type_and_season_mismatch(self):
        ledger = cms_tasks.CmsTaskLedger()
        record = ledger.add(magnet(), "示例剧集", subscribe=SimpleNamespace(
            id=8, tmdbid=100, doubanid=None, type="TV", season=2
        ))
        ledger.update(record["btih"], "pending_organize")
        self.assertEqual("type_mismatch", ledger.diagnose_transfer_complete(tmdb_id=100, media_type="MOVIE", season=2)[1])
        self.assertEqual("season_mismatch", ledger.diagnose_transfer_complete(tmdb_id=100, media_type="TV", season=1)[1])
        matched, status, ids = ledger.diagnose_transfer_complete(tmdb_id=100, media_type="电视剧", season=2)
        self.assertEqual("matched", status)
        self.assertEqual(record["btih"], matched["btih"])
        self.assertEqual([record["btih"]], ids)

    def test_transfer_complete_rejects_ambiguous_records(self):
        ledger = cms_tasks.CmsTaskLedger()
        for char in ("a", "b"):
            record = ledger.add(magnet(char), "示例电影", subscribe=SimpleNamespace(
                id=8, tmdbid=100, doubanid=None, type="MOVIE", season=None
            ))
            ledger.update(record["btih"], "pending_organize")

        self.assertIsNone(ledger.match_transfer_complete(tmdb_id=100, media_type="MOVIE"))
        self.assertEqual("ambiguous", ledger.diagnose_transfer_complete(tmdb_id=100, media_type="MOVIE")[1])

    def test_public_diagnostics_redact_credentials_and_links(self):
        ledger = cms_tasks.CmsTaskLedger()
        record = ledger.add(magnet(), "示例电影", subscribe=SimpleNamespace(
            id=8, tmdbid=100, doubanid=None, type="MOVIE", season=None
        ))
        ledger.update(
            record["btih"], "pending_organize",
            download_name="http://private.invalid/movie Cookie=secret",
            organize_wait_reason="Token=secret https://private.invalid/wait",
        )
        public = ledger.public_records()[0]
        self.assertNotIn("private.invalid", public["download_name"])
        self.assertNotIn("secret", public["download_name"])
        self.assertNotIn("secret", public["organize_wait_reason"])

    def test_unknown_uses_minute_timeout(self):
        now = [datetime(2026, 7, 20, tzinfo=timezone.utc)]
        ledger = cms_tasks.CmsTaskLedger(now=lambda: now[0])
        record = ledger.reserve(
            magnet(),
            "示例电影",
            subscribe=SimpleNamespace(id=8, tmdbid=100, doubanid=None, type="MOVIE", season=None),
            status="unknown",
            source="115_direct",
        )[0]
        now[0] += timedelta(minutes=19)
        result = ledger.reconcile(
            timeout_hours=12,
            direct_timeout_hours=12,
            unknown_timeout_minutes=20,
            subscription_exists=lambda _sid: True,
            history_exists=lambda _record: False,
            restore_subscription=lambda _sid: None,
        )
        self.assertEqual(0, result["timed_out"])
        now[0] += timedelta(minutes=1)
        restored = []
        result = ledger.reconcile(
            timeout_hours=12,
            direct_timeout_hours=12,
            unknown_timeout_minutes=20,
            subscription_exists=lambda _sid: True,
            history_exists=lambda _record: False,
            restore_subscription=restored.append,
        )
        self.assertEqual(1, result["timed_out"])
        self.assertEqual([8], restored)
        self.assertIn("未知状态", record["error"])

    def test_missing_subscription_without_history_is_not_completed(self):
        now = datetime(2026, 7, 20, tzinfo=timezone.utc)
        ledger = cms_tasks.CmsTaskLedger(now=lambda: now)
        ledger.add(magnet(), "示例电影", subscribe=SimpleNamespace(
            id=8, tmdbid=100, doubanid=None, type="MOVIE", season=None
        ))

        result = ledger.reconcile(
            timeout_hours=12,
            subscription_exists=lambda _sid: False,
            history_exists=lambda _record: False,
            restore_subscription=lambda _sid: None,
        )

        self.assertEqual(1, result["failed"])
        self.assertEqual("failed", ledger.records[0]["status"])


if __name__ == "__main__":
    unittest.main()
