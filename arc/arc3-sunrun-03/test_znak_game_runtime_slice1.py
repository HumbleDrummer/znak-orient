from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).with_name("znak_game_runtime_slice1.py")
spec = importlib.util.spec_from_file_location("znak_game_runtime_slice1", MODULE_PATH)
m = importlib.util.module_from_spec(spec)
assert spec.loader is not None
import sys
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def action(action_type, required=(), constraints=None):
    return {
        "action_type": action_type,
        "required_params": list(required),
        "constraints": constraints or {},
    }


class Slice1ContractTests(unittest.TestCase):
    def test_T17_multi_subframe_preservation(self):
        event = m.ObservationEventAdapter.adapt(
            {
                "subframes": [
                    [[0, 0], [0, 0]],
                    [[0, 1], [0, 0]],
                    [[0, 1], [0, 2]],
                ],
                "available_actions": [action("RIGHT")],
                "hard_state": {"terminal_state": "ACTIVE"},
                "settled_subframe_index": 2,
            },
            run_id="R1",
            game_id="G1",
            action_seq=0,
            event_seq=1,
            cause_action_id="A0",
            cause_action_type="RIGHT",
            cause_action_payload={},
        )
        self.assertEqual([s.index for s in event.subframes], [0, 1, 2])
        self.assertEqual(len({s.frame_hash for s in event.subframes}), 3)
        self.assertEqual(event.settled_subframe_index, 2)
        self.assertEqual(event.cause_action_id, "A0")

    def test_T18_delayed_effect_attribution(self):
        event = m.ObservationEventAdapter.adapt(
            {
                "subframes": [
                    {"x": 1, "phase": "none"},
                    {"x": 1, "phase": "animation"},
                    {"x": 2, "phase": "settled"},
                ],
                "available_actions": [action("RIGHT")],
                "hard_state": {"terminal_state": "ACTIVE"},
            },
            run_id="R1",
            game_id="G1",
            action_seq=0,
            event_seq=2,
            cause_action_id="move-000",
            cause_action_type="RIGHT",
            cause_action_payload={},
        )
        self.assertEqual(event.cause_action_id, "move-000")
        self.assertEqual(event.subframes[0].grid["x"], 1)
        self.assertEqual(event.subframes[1].grid["phase"], "animation")
        self.assertEqual(event.subframes[2].grid["x"], 2)
        self.assertEqual(event.settled_subframe_index, 2)

    def test_T19_missing_parameter_rejected(self):
        event = m.ObservationEventAdapter.adapt(
            {
                "frame": [[0]],
                "available_actions": [
                    action(
                        "POINT",
                        required=("x", "y"),
                        constraints={"x": {"min": 0, "max": 63}, "y": {"min": 0, "max": 63}},
                    )
                ],
                "hard_state": {"terminal_state": "ACTIVE"},
            },
            run_id="R1",
            game_id="G1",
            action_seq=0,
            event_seq=1,
        )
        auth = m.ActionContract.authorize(m.ActionCandidate("POINT", {"x": 3}), event)
        self.assertFalse(auth.legal)
        self.assertEqual(auth.reason_code, "MISSING_REQUIRED_PARAM:y")
        self.assertIsNone(auth.dispatch_payload)

    def test_T20_unavailable_action_rejected(self):
        event = m.ObservationEventAdapter.adapt(
            {
                "frame": [[0]],
                "available_actions": [action("LEFT"), action("RIGHT")],
                "hard_state": {"terminal_state": "ACTIVE"},
            },
            run_id="R1",
            game_id="G1",
            action_seq=0,
            event_seq=1,
        )
        auth = m.ActionContract.authorize(m.ActionCandidate("UP", {}), event)
        self.assertFalse(auth.legal)
        self.assertEqual(auth.reason_code, "ACTION_UNAVAILABLE")
        self.assertIsNone(auth.dispatch_payload)

    def test_T30_deterministic_derived_replay(self):
        def run_once():
            rt = m.Slice1Runtime()
            obs = m.ObservationEventAdapter.adapt(
                {
                    "frame": [[0, 1], [0, 0]],
                    "available_actions": [action("RIGHT")],
                    "hard_state": {"terminal_state": "ACTIVE", "level_counter": 1},
                    "level_id": "L1",
                },
                run_id="R1",
                game_id="G1",
                action_seq=0,
                event_seq=1,
                source_ref="fixture/T30/before",
            )
            candidate = m.ActionCandidate("RIGHT", {})
            auth = rt.prepare_action(
                observation=obs,
                action_seq=0,
                candidate=candidate,
                prediction={"expected": {"self": [0, 2]}, "confidence": 0.9},
            )
            self.assertTrue(auth.legal)
            result = m.ObservationEventAdapter.adapt(
                {
                    "subframes": [
                        [[0, 1], [0, 0]],
                        [[0, 0, 1], [0, 0, 0]],
                    ],
                    "available_actions": [action("LEFT"), action("RIGHT")],
                    "hard_state": {"terminal_state": "ACTIVE", "level_counter": 1},
                    "level_id": "L1",
                    "settled_subframe_index": 1,
                },
                run_id="R1",
                game_id="G1",
                action_seq=0,
                event_seq=2,
                cause_action_id="action-0",
                cause_action_type="RIGHT",
                cause_action_payload={},
                source_ref="fixture/T30/after",
            )
            rt.record_result(
                action_seq=0,
                result_event=result,
                actual_effect={"self_delta": [0, 1]},
            )
            return obs.event_hash, result.event_hash, rt.trace.trace_hash, rt.trace.canonical_snapshot()

        a = run_once()
        b = run_once()
        self.assertEqual(a, b)

    def test_previous_outcome_required_before_next_decision(self):
        rt = m.Slice1Runtime()
        obs = m.ObservationEventAdapter.adapt(
            {
                "frame": [[0]],
                "available_actions": [action("WAIT")],
                "hard_state": {"terminal_state": "ACTIVE"},
            },
            run_id="R1", game_id="G1", action_seq=0, event_seq=1,
        )
        rt.prepare_action(
            observation=obs,
            action_seq=0,
            candidate=m.ActionCandidate("WAIT", {}),
            prediction={"expected": "no_change"},
        )
        with self.assertRaises(ValueError):
            rt.prepare_action(
                observation=obs,
                action_seq=1,
                candidate=m.ActionCandidate("WAIT", {}),
                prediction={"expected": "no_change"},
            )

    def test_terminal_state_blocks_action(self):
        event = m.ObservationEventAdapter.adapt(
            {
                "frame": [[0]],
                "available_actions": [action("LEFT")],
                "hard_state": {"terminal_state": "GAME_OVER"},
            },
            run_id="R1", game_id="G1", action_seq=0, event_seq=1,
        )
        auth = m.ActionContract.authorize(m.ActionCandidate("LEFT", {}), event)
        self.assertFalse(auth.legal)
        self.assertEqual(auth.reason_code, "HARD_TERMINAL_STATE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
