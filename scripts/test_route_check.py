#!/usr/bin/env python3

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("route_check.py")


class RouteCheckCliTests(unittest.TestCase):
    def run_cli(self, directory: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False,
        )

    def init_state(self, directory: Path, task_class: str = "long") -> Path:
        state = directory / ".route" / "state.json"
        result = self.run_cli(
            directory,
            "init",
            "--state",
            str(state),
            "--task-class",
            task_class,
            "--goal",
            "verify the route",
            "--acceptance",
            "the check passes",
            "--constraint",
            "preserve user changes",
            "--route-assumption",
            "the current interface is sufficient",
            "--route-probe",
            "run the focused check",
            "--failure-criterion",
            "the interface cannot express the required behavior",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return state

    def record(
        self,
        directory: Path,
        state: Path,
        *extra: str,
    ) -> subprocess.CompletedProcess[str]:
        return self.run_cli(
            directory,
            "record",
            "--state",
            str(state),
            *extra,
        )

    def candidate(self, identifier: str) -> str:
        return json.dumps(
            {
                "id": identifier,
                "assumption": f"route {identifier} can satisfy the goal",
                "probe": f"run the smallest probe for {identifier}",
                "failure_criterion": f"probe {identifier} contradicts its assumption",
                "cost": "small",
                "risk": "low",
            }
        )

    def test_single_failure_does_not_stale_route(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            state = self.init_state(directory)
            result = self.record(
                directory,
                state,
                "--result",
                "fail",
                "--progress",
                "none",
                "--failure-signature",
                "same assertion",
                "--checkpoint",
                "check-1",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            status = self.run_cli(directory, "status", "--state", str(state))
            self.assertIn("STATUS: ROUTE_HEALTHY", status.stdout)

    def test_repeated_failure_requires_approval_before_route_change(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            state = self.init_state(directory)
            for checkpoint in ("check-1", "check-2"):
                result = self.record(
                    directory,
                    state,
                    "--result",
                    "fail",
                    "--progress",
                    "none",
                    "--failure-signature",
                    "same assertion",
                    "--checkpoint",
                    checkpoint,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

            status = self.run_cli(directory, "status", "--state", str(state))
            self.assertIn("STATUS: ROUTE_STALE", status.stdout)

            prepare = self.run_cli(directory, "packet", "--state", str(state))
            self.assertEqual(prepare.returncode, 0, prepare.stderr)
            self.assertIn("STATUS: REPLAN_REQUIRED", prepare.stdout)

            packet = self.run_cli(
                directory,
                "packet",
                "--state",
                str(state),
                "--candidate",
                self.candidate("A"),
                "--candidate",
                self.candidate("B"),
            )
            self.assertEqual(packet.returncode, 0, packet.stderr)
            self.assertIn("Choose: A / B / current route / stop", packet.stdout)

            blocked = self.record(
                directory,
                state,
                "--route-id",
                "B",
                "--result",
                "unknown",
            )
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("requires explicit approval", blocked.stderr)

            approved = self.run_cli(
                directory,
                "approve",
                "--state",
                str(state),
                "--choice",
                "B",
                "--user-text",
                "User selected B",
            )
            self.assertEqual(approved.returncode, 0, approved.stderr)
            data = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(data["route"]["id"], "B")
            self.assertEqual(data["route_generation"], 1)
            self.assertEqual(data["status"], "ROUTE_HEALTHY")
            self.assertFalse(data["approval_required"])

    def test_contradicted_assumption_freezes_route(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            state = self.init_state(directory)
            result = self.record(
                directory,
                state,
                "--result",
                "fail",
                "--progress",
                "negative",
                "--assumption-status",
                "contradicted",
                "--failure-signature",
                "unsupported behavior",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("STATUS: ROUTE_STALE", result.stdout)
            self.assertIn("assumption_falsified", result.stdout)

    def test_constraint_violation_freezes_route(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            state = self.init_state(directory)
            result = self.record(
                directory,
                state,
                "--result",
                "fail",
                "--constraint-status",
                "violated",
                "--failure-signature",
                "hard constraint",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("STATUS: ROUTE_STALE", result.stdout)
            self.assertIn("constraint_violation", result.stdout)

    def test_promote_short_task_records_unknown_history(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            state = directory / ".route" / "state.json"
            result = self.run_cli(
                directory,
                "promote",
                "--state",
                str(state),
                "--goal",
                "a short task that grew",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(data["task_class"], "short")
            self.assertEqual(data["history_before_tracking"], "unknown")
            self.assertEqual(data["tracking_mode"], "full")

    def test_acceptance_pass_marks_done(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            state = self.init_state(directory)
            result = self.record(
                directory,
                state,
                "--result",
                "pass",
                "--acceptance",
                "pass",
                "--progress",
                "positive",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("STATUS: DONE", result.stdout)

    def test_observation_window_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            state = self.init_state(directory)
            for index in range(6):
                result = self.record(
                    directory,
                    state,
                    "--result",
                    "unknown",
                    "--progress",
                    "positive",
                    "--checkpoint",
                    f"check-{index}",
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(len(data["observations"]), 4)
            self.assertEqual(data["observations"][0]["checkpoint"], "check-2")

    def test_stop_choice_is_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            state = self.init_state(directory)
            for _ in range(2):
                result = self.record(
                    directory,
                    state,
                    "--result",
                    "fail",
                    "--progress",
                    "none",
                    "--failure-signature",
                    "blocked",
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            packet = self.run_cli(
                directory,
                "packet",
                "--state",
                str(state),
                "--candidate",
                self.candidate("A"),
                "--candidate",
                self.candidate("B"),
            )
            self.assertEqual(packet.returncode, 0, packet.stderr)
            stopped = self.run_cli(
                directory,
                "approve",
                "--state",
                str(state),
                "--choice",
                "stop",
                "--user-text",
                "Stop here",
            )
            self.assertEqual(stopped.returncode, 0, stopped.stderr)
            after = self.record(directory, state, "--result", "unknown")
            self.assertNotEqual(after.returncode, 0)
            self.assertIn("task is stopped", after.stderr)

    def test_continue_current_route_resets_stale_window(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            state = self.init_state(directory)
            for _ in range(2):
                result = self.record(
                    directory,
                    state,
                    "--result",
                    "fail",
                    "--progress",
                    "none",
                    "--failure-signature",
                    "blocked",
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            packet = self.run_cli(
                directory,
                "packet",
                "--state",
                str(state),
                "--candidate",
                self.candidate("A"),
                "--candidate",
                self.candidate("B"),
            )
            self.assertEqual(packet.returncode, 0, packet.stderr)
            continued = self.run_cli(
                directory,
                "approve",
                "--state",
                str(state),
                "--choice",
                "current route",
                "--user-text",
                "Continue the current route",
            )
            self.assertEqual(continued.returncode, 0, continued.stderr)
            data = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "ROUTE_HEALTHY")
            self.assertEqual(data["observations"], [])
            self.assertEqual(data["route_generation"], 0)
            self.assertEqual(data["route_history"][-1]["decision"], "continue_current")


if __name__ == "__main__":
    unittest.main()
