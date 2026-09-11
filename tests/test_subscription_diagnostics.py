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
