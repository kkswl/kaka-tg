import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "plugins.v2" / "tgsearch115"
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
timeline_module, health_module = load("subscription_timeline"), load("source_health")

class DiagnosticTest(unittest.TestCase):
    def test_seasons_have_independent_timeline_and_restart_recovers_running(self):
        timeline = timeline_module.SubscriptionTimeline()
        a = timeline.start(SimpleNamespace(id=7, name="Example", year=2024, season=2), "periodic")
        b = timeline.start(SimpleNamespace(id=7, name="Example", year=2024, season=3), "periodic")
        self.assertNotEqual(a, b)
        restored = timeline_module.SubscriptionTimeline(timeline.dump())
        self.assertEqual("recovered", restored.list()["items"][0]["status"])

    def test_terminal_clear_requires_no_active_run(self):
        timeline = timeline_module.SubscriptionTimeline()
        run = timeline.start(SimpleNamespace(id=8, name="Example", year=None, season=None), "periodic")
        with self.assertRaises(RuntimeError): timeline.clear_terminal()
        timeline.event(run, "skipped", "skipped", "safe reject")
        self.assertEqual(1, timeline.clear_terminal())

    def test_terminal_clear_keeps_only_terminal_records_and_reports_counts(self):
        timeline = timeline_module.SubscriptionTimeline()
        terminal = timeline.start(SimpleNamespace(id=10, name="Terminal", year=None, season=None), "periodic")
        timeline.event(terminal, "completed", "completed", "done")
        self.assertEqual({"total": 1, "active_count": 0, "terminal_count": 1}, timeline.counts())
        persisted = timeline.dump()
        self.assertEqual(1, timeline.clear_terminal())
        self.assertEqual({"total": 0, "active_count": 0, "terminal_count": 0}, timeline.counts())
        self.assertEqual([], timeline_module.SubscriptionTimeline(timeline.dump()).dump())
        self.assertEqual("completed", persisted[0]["status"])

    def test_list_includes_full_terminal_count_when_page_is_limited(self):
        timeline = timeline_module.SubscriptionTimeline()
        for number in range(12):
            run = timeline.start(SimpleNamespace(id=100 + number, name="Terminal", year=None, season=None), "periodic")
            timeline.event(run, "skipped", "skipped", "done")
        listing = timeline.list(limit=10)
        self.assertEqual(12, listing["total"])
        self.assertEqual(12, listing["terminal_count"])
        self.assertEqual(10, len(listing["items"]))

    def test_waiting_status_is_protected_from_terminal_clear(self):
        timeline = timeline_module.SubscriptionTimeline()
        run = timeline.start(SimpleNamespace(id=11, name="Waiting", year=None, season=None), "periodic")
        timeline.event(run, "waiting", "waiting", "waiting safely")
        self.assertEqual(1, timeline.counts()["active_count"])
        with self.assertRaises(RuntimeError):
            timeline.clear_terminal()

    def test_task_completion_updates_latest_subscription_season(self):
        timeline = timeline_module.SubscriptionTimeline()
        timeline.start(SimpleNamespace(id=12, name="Example", year=2024, season=2), "periodic")
        timeline.start(SimpleNamespace(id=12, name="Example", year=2024, season=3), "periodic")
        changed = timeline.event_for_subscription(
            12, 2, "completed", "completed", "MoviePilot 整理已确认",
            btih_prefix="a" * 12, task_status="completed",
        )
        self.assertTrue(changed)
        by_season = {item["season"]: item for item in timeline.list()["items"]}
        self.assertEqual("completed", by_season[2]["status"])
        self.assertEqual("running", by_season[3]["status"])
        self.assertEqual("a" * 12, by_season[2]["btih_prefix"])

    def test_timeline_sanitizes_links_and_bounds_events(self):
        timeline = timeline_module.SubscriptionTimeline(max_events=10)
        run = timeline.start(SimpleNamespace(id=9, name="Example", year=None, season=None), "periodic")
        timeline.event(run, "failed", "failed", "see https://secret.invalid/path magnet:?xt=urn:btih:x")
        item = timeline.list()["items"][0]
        self.assertNotIn("secret.invalid", item["reason"])
        self.assertNotIn("magnet:?", item["reason"])

    def test_source_health_empty_is_not_failure_and_throttle_lowers_score(self):
        health = health_module.SourceHealth(); health.record("tg", "empty", 1.0); health.record("site", "success", 2.0, 3)
        health.record("tg", "429", 1.0)
        snapshot = health.snapshot()
        self.assertEqual(1, snapshot["tg"]["empty"])
        self.assertEqual(1, snapshot["tg"]["http_429"])
        self.assertLess(snapshot["tg"]["score"], snapshot["site"]["score"])

if __name__ == "__main__": unittest.main()
