import importlib.util
import sys
import threading
import time
import unittest
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "plugins.v2" / "tgsearch115" / "recognition_control.py"
spec = importlib.util.spec_from_file_location("tgsearch115_recognition_control", PATH)
control = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = control
spec.loader.exec_module(control)


class RecognitionControlTest(unittest.TestCase):
    def test_concurrent_calls_are_serialized(self):
        gate = control.RecognitionGate(sleep=lambda _: None)
        active = 0
        max_active = 0
        guard = threading.Lock()

        def operation(_chain):
            nonlocal active, max_active
            with guard:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.02)
            with guard:
                active -= 1
            return "ok"

        results = []
        threads = [threading.Thread(
            target=lambda: results.append(gate.run(object, operation))
        ) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2)

        self.assertEqual(6, len(results))
        self.assertEqual(1, max_active)
        self.assertEqual(1, gate.status()["max_active"])

    def test_kill_cursor_recreates_chain_and_retries_once(self):
        factories = []

        def factory():
            item = object()
            factories.append(item)
            return item

        calls = 0

        def operation(chain):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise AttributeError("'NoneType' object has no attribute 'kill_cursor'")
            return chain

        gate = control.RecognitionGate(
            sleep=lambda _: None, random_uniform=lambda _a, _b: 1
        )
        result = gate.run(factory, operation, label="candidate")

        self.assertIs(result, factories[1])
        self.assertEqual(2, len(factories))
        self.assertEqual(1, gate.status()["retries"])

    def test_second_cursor_failure_becomes_unavailable(self):
        gate = control.RecognitionGate(
            sleep=lambda _: None, random_uniform=lambda _a, _b: 1
        )
        with self.assertRaises(control.RecognitionUnavailable):
            gate.run(
                object,
                lambda _chain: (_ for _ in ()).throw(
                    AttributeError("'NoneType' object has no attribute 'kill_cursor'")
                ),
            )
        self.assertEqual(1, gate.status()["identity_unavailable"])

    def test_empty_result_recreates_chain_then_becomes_unavailable(self):
        factories = []
        gate = control.RecognitionGate(
            sleep=lambda _: None, random_uniform=lambda _a, _b: 1
        )
        with self.assertRaises(control.RecognitionUnavailable):
            gate.run(
                lambda: factories.append(object()) or factories[-1],
                lambda _chain: None,
                retry_none=True,
            )
        self.assertEqual(2, len(factories))
        self.assertEqual(1, gate.status()["retries"])

    def test_stop_rejects_new_recognition(self):
        gate = control.RecognitionGate(sleep=lambda _: None)
        self.assertTrue(gate.stop())
        with self.assertRaises(control.RecognitionUnavailable):
            gate.run(object, lambda _chain: "unexpected")

    def test_stop_waits_for_current_call_and_leaves_no_worker(self):
        gate = control.RecognitionGate(sleep=lambda _: None)
        entered = threading.Event()
        release = threading.Event()

        def operation(_chain):
            entered.set()
            release.wait(timeout=1)
            return "ok"

        worker = threading.Thread(target=lambda: gate.run(object, operation))
        worker.start()
        self.assertTrue(entered.wait(timeout=1))
        self.assertFalse(gate.stop(timeout=0.01))
        release.set()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertTrue(gate.stop(timeout=1))


if __name__ == "__main__":
    unittest.main()
