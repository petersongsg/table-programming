"""
table-programming / tests/test_rule_engine.py
==================================================
Unit tests for the rule engine.

Covers:
- Rule dataclass + load_rules()
- make_snapshot() isolation
- Priority preemption (first hit wins, rest skipped)
- Action registry dispatch
- Thread-safe snapshot copy (no aliasing)
- eval namespace includes `time`
- Exception in cond is caught, rule skipped

Run:  python -m unittest test_rule_engine.py -v
"""
import sys
import time
import threading
import unittest
from pathlib import Path

# Make project root importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from main import (
    Rule,
    load_rules,
    make_snapshot,
)
from context import RobotContext
import action_plugins as ap


class TestRuleDataclass(unittest.TestCase):
    def test_rule_fields(self):
        r = Rule(name="t", source_plugins=["s"], condition_expr="True", action_plugin="action_full_stop")
        self.assertEqual(r.name, "t")
        self.assertEqual(r.source_plugins, ["s"])
        self.assertEqual(r.condition_expr, "True")
        self.assertEqual(r.action_plugin, "action_full_stop")


class TestLoadRules(unittest.TestCase):
    def test_load_real_rules_file(self):
        path = ROOT / "rules.json"
        if not path.exists():
            self.skipTest("rules.json not found")
        rules = load_rules(str(path))
        self.assertGreater(len(rules), 0)
        for r in rules:
            self.assertTrue(r.name)
            self.assertTrue(r.action_plugin in ap.ACTION_PLUGIN_REGISTRY,
                            f"{r.action_plugin} not in registry")


class TestSnapshot(unittest.TestCase):
    def test_snapshot_is_isolated(self):
        ctx = RobotContext(front_dist=1.0, task_stage="idle")
        snap = make_snapshot(ctx)
        # Mutate original ctx
        ctx.front_dist = 5.0
        ctx.task_stage = "modified"
        # Snapshot must NOT change
        self.assertAlmostEqual(snap.front_dist, 1.0)
        self.assertEqual(snap.task_stage, "idle")

    def test_snapshot_default_values(self):
        ctx = RobotContext()
        snap = make_snapshot(ctx)
        self.assertAlmostEqual(snap.front_dist, 1.0)
        self.assertFalse(snap.emergency_btn)
        self.assertEqual(snap.task_stage, "idle")
        self.assertAlmostEqual(snap.ts_io, 0.0)


class TestActionRegistry(unittest.TestCase):
    def test_all_required_actions_registered(self):
        for name in [
            "action_full_stop",
            "action_brake",
            "action_move_forward",
            "action_gripper_close",
            "action_set_go_pick",
            "action_set_gripping",
            "action_set_go_drop",
        ]:
            self.assertIn(name, ap.ACTION_PLUGIN_REGISTRY)

    def test_full_stop_clears_state(self):
        ctx = RobotContext(speed=1.0, task_stage="go_pick")
        ap.ACTION_PLUGIN_REGISTRY["action_full_stop"](ctx)
        self.assertAlmostEqual(ctx.speed, 0.0)
        self.assertEqual(ctx.task_stage, "idle")

    def test_set_go_pick_transitions_state(self):
        ctx = RobotContext(task_stage="idle")
        ap.ACTION_PLUGIN_REGISTRY["action_set_go_pick"](ctx)
        self.assertEqual(ctx.task_stage, "go_pick")


class TestPriorityPreemption(unittest.TestCase):
    """Simulate the main_loop priority preemption logic in isolation."""

    def _simulate_one_cycle(self, ctx, rules, eval_globals=None):
        """Returns the name of the rule that fired (or None)."""
        snap = make_snapshot(ctx)
        for r in rules:
            if not r.action_plugin in ap.ACTION_PLUGIN_REGISTRY:
                continue
            try:
                ns = {"time": time, **(eval_globals or {})}
                ok = eval(r.condition_expr, ns, snap.__dict__)
            except Exception:
                continue
            if ok:
                ap.ACTION_PLUGIN_REGISTRY[r.action_plugin](ctx)
                return r.name
        return None

    def test_first_hit_wins(self):
        rules = [
            Rule(name="stop",    source_plugins=[], condition_expr="True", action_plugin="action_full_stop"),
            Rule(name="forward", source_plugins=[], condition_expr="True", action_plugin="action_move_forward"),
        ]
        ctx = RobotContext(speed=5.0, task_stage="go_pick")
        fired = self._simulate_one_cycle(ctx, rules)
        self.assertEqual(fired, "stop")
        # forward must NOT have fired (preemption)
        self.assertEqual(ctx.task_stage, "idle")

    def test_no_hit_does_nothing(self):
        rules = [
            Rule(name="forward", source_plugins=[], condition_expr="False", action_plugin="action_move_forward"),
        ]
        ctx = RobotContext(speed=0.0, task_stage="idle")
        fired = self._simulate_one_cycle(ctx, rules)
        self.assertIsNone(fired)
        self.assertAlmostEqual(ctx.speed, 0.0)
        self.assertEqual(ctx.task_stage, "idle")

    def test_eval_namespace_has_time(self):
        """time module must be available inside eval namespace; ts_io from 2000s ago → fire."""
        rules = [
            Rule(name="ts", source_plugins=[], condition_expr="(time.time() - ts_io) > 1000", action_plugin="action_full_stop"),
        ]
        ctx = RobotContext(ts_io=time.time() - 2000.0)  # 2000s ago
        fired = self._simulate_one_cycle(ctx, rules)
        self.assertEqual(fired, "ts")

    def test_eval_namespace_has_time_no_fire(self):
        """Fresh ts_io (now) → no fire (delta ~0)."""
        rules = [
            Rule(name="ts", source_plugins=[], condition_expr="(time.time() - ts_io) > 1000", action_plugin="action_full_stop"),
        ]
        ctx = RobotContext(ts_io=time.time())  # now
        fired = self._simulate_one_cycle(ctx, rules)
        self.assertIsNone(fired)

    def test_exception_skipped_continues(self):
        rules = [
            Rule(name="bad",   source_plugins=[], condition_expr="this_does_not_exist", action_plugin="action_full_stop"),
            Rule(name="good",  source_plugins=[], condition_expr="True", action_plugin="action_move_forward"),
        ]
        ctx = RobotContext(speed=0.0, task_stage="idle")
        fired = self._simulate_one_cycle(ctx, rules)
        # bad raises, gets skipped; good fires
        self.assertEqual(fired, "good")
        self.assertAlmostEqual(ctx.speed, 0.4)


class TestThreadSafeSnapshot(unittest.TestCase):
    def test_snapshot_under_concurrent_writes(self):
        """Background writer updates ctx; main thread snapshots — must be consistent."""
        ctx = RobotContext()
        lock = threading.Lock()
        errors = []

        def writer():
            for i in range(1000):
                with lock:
                    ctx.front_dist = float(i)
                    ctx.ts_io = time.time()

        def reader():
            for _ in range(1000):
                with lock:
                    snap = make_snapshot(ctx)
                # If read is consistent, snap.front_dist should be a number;
                # we don't assert ordering — we assert no torn read (TypeError/AttributeError)
                if not isinstance(snap.front_dist, float):
                    errors.append("non-float front_dist")

        t1 = threading.Thread(target=writer, daemon=True)
        t2 = threading.Thread(target=reader, daemon=True)
        t1.start(); t2.start()
        t1.join(); t2.join()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
