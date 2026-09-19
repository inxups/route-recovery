#!/usr/bin/env python3
"""Small, standard-library-only state machine for route recovery."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATUSES = (
    "ROUTE_HEALTHY",
    "ROUTE_STALE",
    "REPLAN_REQUIRED",
    "WAITING_FOR_USER",
    "DONE",
)
MAX_OBSERVATIONS = 4
MAX_ROUTE_HISTORY = 3


class StateError(Exception):
    """Expected user-facing state or argument error."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.strip().lower())


def compact(value: Any, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def values(value: list[str] | None) -> list[str]:
    return [item for item in (value or []) if item]


def git_snapshot() -> dict[str, str | None]:
    def run(args: list[str]) -> str | None:
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None

    return {
        "commit": run(["git", "rev-parse", "HEAD"]),
        "status": run(["git", "status", "--short"]),
        "diff_stat": run(["git", "diff", "--stat"]),
    }


def state_path(raw: str) -> Path:
    return Path(raw).expanduser()


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise StateError(f"state file does not exist: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"cannot read state file {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != 1:
        raise StateError(f"unsupported state file: {path}")
    return data


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now()
    fd, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, ensure_ascii=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def option(args: argparse.Namespace, name: str, default: Any = None) -> Any:
    return getattr(args, name, default)


def make_state(
    args: argparse.Namespace,
    task_class: str,
    history_before_tracking: str | None = None,
) -> dict[str, Any]:
    return {
        "version": 1,
        "task_class": task_class,
        "tracking_mode": "full",
        "goal": option(args, "goal", ""),
        "acceptance": values(option(args, "acceptance", [])),
        "constraints": values(option(args, "constraints", [])),
        "baseline": git_snapshot(),
        "route": {
            "id": option(args, "route_id", "initial"),
            "assumption": option(args, "route_assumption", ""),
            "probe": option(args, "route_probe", ""),
            "failure_criterion": option(args, "failure_criterion", ""),
        },
        "observations": [],
        "verified_facts": values(option(args, "verified_fact", [])),
        "unverified_assumptions": values(
            option(args, "unverified_assumption", [])
        ),
        "open_uncertainties": values(option(args, "uncertainty", [])),
        "next_probes": values(option(args, "next_probe", [])),
        "route_generation": 0,
        "approval_required": False,
        "pending_candidates": [],
        "approval": None,
        "route_history": [],
        "status": "ROUTE_HEALTHY",
        "reasons": [],
        "terminal": False,
        "history_before_tracking": history_before_tracking,
        "created_at": now(),
        "updated_at": now(),
    }


def update_lists(state: dict[str, Any], args: argparse.Namespace) -> None:
    for field, argument in (
        ("verified_facts", "verified_fact"),
        ("unverified_assumptions", "unverified_assumption"),
        ("open_uncertainties", "uncertainty"),
        ("next_probes", "next_probe"),
    ):
        additions = values(option(args, argument, []))
        if additions:
            existing = list(state.get(field, []))
            for item in additions:
                if item not in existing:
                    existing.append(item)
            state[field] = existing[-8:]


def trailing_failure_streak(observations: list[dict[str, Any]]) -> int:
    if not observations:
        return 0
    latest = observations[-1]
    signature = latest.get("failure_signature", "")
    if not signature or latest.get("progress") == "positive":
        return 0
    streak = 0
    for observation in reversed(observations):
        if observation.get("progress") == "positive":
            break
        if observation.get("failure_signature") != signature:
            break
        streak += 1
    return streak


def trailing_no_progress(observations: list[dict[str, Any]]) -> int:
    streak = 0
    for observation in reversed(observations):
        if observation.get("progress") != "none":
            break
        streak += 1
    return streak


def trailing_action_streak(observations: list[dict[str, Any]]) -> int:
    if not observations:
        return 0
    signature = observations[-1].get("action_signature", "")
    if not signature:
        return 0
    streak = 0
    for observation in reversed(observations):
        if observation.get("progress") == "positive":
            break
        if observation.get("action_signature") != signature:
            break
        streak += 1
    return streak


def evaluate(state: dict[str, Any]) -> tuple[str, list[str]]:
    status = state.get("status", "ROUTE_HEALTHY")
    if state.get("terminal"):
        return status, list(state.get("reasons", []))
    if status == "WAITING_FOR_USER":
        return status, list(state.get("reasons", []))
    if status == "REPLAN_REQUIRED":
        return status, list(state.get("reasons", []))

    observations = list(state.get("observations", []))
    if observations and observations[-1].get("acceptance") == "pass":
        return "DONE", []
    if status == "ROUTE_STALE":
        return status, list(state.get("reasons", []))

    if not observations:
        return "ROUTE_HEALTHY", []

    reasons: list[str] = []
    latest = observations[-1]
    if latest.get("constraint") == "violated":
        reasons.append("constraint_violation")
    if latest.get("assumption") == "contradicted":
        reasons.append("assumption_falsified")
    if trailing_failure_streak(observations) >= 2:
        reasons.append("repeated_failure")
    if trailing_no_progress(observations) >= 2:
        reasons.append("no_progress")
    if trailing_action_streak(observations) >= 2:
        reasons.append("repeated_failure")
    if len(observations) >= 2:
        previous = observations[-2]
        if (
            latest.get("complexity") == "higher"
            and latest.get("progress") in ("none", "negative")
            and previous.get("progress") in ("none", "negative")
        ):
            reasons.append("complexity_growth")

    if reasons:
        unique = list(dict.fromkeys(reasons))
        return "ROUTE_STALE", unique
    return "ROUTE_HEALTHY", []


def apply_evaluation(state: dict[str, Any]) -> None:
    status, reasons = evaluate(state)
    state["status"] = status
    state["reasons"] = reasons


def ensure_route_unchanged(
    state: dict[str, Any], args: argparse.Namespace
) -> None:
    route_id = option(args, "route_id")
    generation = option(args, "route_generation")
    current_id = state.get("route", {}).get("id")
    current_generation = state.get("route_generation", 0)
    if route_id and route_id != current_id:
        raise StateError(
            "route change requires explicit approval; use approve first"
        )
    if generation is not None and generation != current_generation:
        raise StateError(
            "route generation change requires explicit approval; use approve first"
        )


def observation_from_args(
    state: dict[str, Any], args: argparse.Namespace
) -> dict[str, Any]:
    signature = compact(normalize(option(args, "failure_signature", "")))
    action = compact(normalize(option(args, "action_signature", "")))
    return {
        "at": now(),
        "route_generation": state.get("route_generation", 0),
        "route_id": state.get("route", {}).get("id", "initial"),
        "result": option(args, "result", "unknown"),
        "acceptance": option(args, "acceptance", "unknown"),
        "failure_signature": signature,
        "action_signature": action,
        "progress": option(args, "progress", "unknown"),
        "complexity": option(args, "complexity", "unknown"),
        "assumption": option(args, "assumption_status", "unverified"),
        "constraint": option(args, "constraint_status", "unknown"),
        "expected": compact(option(args, "expected", ""), 500),
        "observed": compact(option(args, "observed", ""), 500),
        "reproducibility": compact(option(args, "reproducibility", ""), 180),
        "checkpoint": compact(option(args, "checkpoint", ""), 180),
        "evidence": compact(option(args, "evidence", ""), 240),
    }


def history_observation(observation: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "at",
        "route_generation",
        "route_id",
        "result",
        "acceptance",
        "failure_signature",
        "progress",
        "complexity",
        "assumption",
        "constraint",
        "checkpoint",
        "evidence",
    )
    return {
        field: compact(observation.get(field, ""), 180)
        if field not in ("route_generation",)
        else observation.get(field)
        for field in fields
    }


def print_status(state: dict[str, Any]) -> None:
    status, reasons = evaluate(state)
    print(f"STATUS: {status}")
    if reasons:
        print(f"REASONS: {', '.join(reasons)}")
    if status in ("ROUTE_STALE", "REPLAN_REQUIRED"):
        print("NEXT: prepare at least two candidates and request user approval")
    elif status == "WAITING_FOR_USER":
        if state.get("terminal"):
            print("NEXT: stopped by user")
        else:
            print("NEXT: wait for an explicit route choice")
    elif status == "DONE":
        print("NEXT: no route recovery action")
    else:
        print("NEXT: continue the current route until the next checkpoint")


def command_init(args: argparse.Namespace) -> int:
    path = state_path(args.state)
    if path.exists():
        raise StateError(f"state file already exists: {path}")
    if not args.goal:
        raise StateError("--goal is required")
    state = make_state(args, args.task_class)
    save_state(path, state)
    print(f"initialized {path}")
    print_status(state)
    return 0


def command_promote(args: argparse.Namespace) -> int:
    path = state_path(args.state)
    if path.exists():
        state = load_state(path)
        if state.get("terminal"):
            raise StateError("cannot promote a stopped task")
        state["tracking_mode"] = "full"
        state["history_before_tracking"] = "unknown"
        update_lists(state, args)
    else:
        if not args.goal:
            raise StateError("--goal is required when promoting without state")
        state = make_state(args, "short", "unknown")
    save_state(path, state)
    print(f"promoted {path}")
    print_status(state)
    return 0


def command_record(args: argparse.Namespace) -> int:
    path = state_path(args.state)
    state = load_state(path)
    if state.get("terminal"):
        raise StateError("task is stopped; no further observations are accepted")
    ensure_route_unchanged(state, args)
    observation = observation_from_args(state, args)
    observations = list(state.get("observations", []))
    observations.append(observation)
    state["observations"] = observations[-MAX_OBSERVATIONS:]
    update_lists(state, args)
    apply_evaluation(state)
    save_state(path, state)
    print_status(state)
    return 0


def candidate_from_json(raw: str) -> dict[str, Any]:
    try:
        candidate = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StateError(f"candidate must be JSON: {exc}") from exc
    if not isinstance(candidate, dict):
        raise StateError("candidate must be a JSON object")
    required = ("id", "assumption", "probe", "failure_criterion")
    missing = [field for field in required if not candidate.get(field)]
    if missing:
        raise StateError(
            "candidate is missing: " + ", ".join(missing)
        )
    return {
        "id": compact(candidate["id"], 40),
        "assumption": compact(candidate["assumption"], 240),
        "probe": compact(candidate["probe"], 240),
        "failure_criterion": compact(candidate["failure_criterion"], 240),
        "cost": compact(candidate.get("cost", ""), 120),
        "risk": compact(candidate.get("risk", ""), 120),
        "checkpoint": compact(candidate.get("checkpoint", ""), 180),
        "evidence": compact(candidate.get("evidence", ""), 240),
    }


def packet_lines(state: dict[str, Any]) -> list[str]:
    lines = [
        "Goal: " + compact(state.get("goal", "")),
        "Acceptance criteria: "
        + compact("; ".join(state.get("acceptance", [])) or "unspecified"),
        "Constraints: "
        + compact("; ".join(state.get("constraints", [])) or "none recorded"),
        "Baseline: "
        + compact(json.dumps(state.get("baseline", {}), ensure_ascii=True)),
        "Verified facts: "
        + compact("; ".join(state.get("verified_facts", [])) or "none recorded"),
        "Unverified assumptions: "
        + compact(
            "; ".join(state.get("unverified_assumptions", []))
            or "none recorded"
        ),
        "Open uncertainties: "
        + compact(
            "; ".join(state.get("open_uncertainties", [])) or "none recorded"
        ),
        "Failed routes and evidence:",
    ]
    failures = [
        observation
        for observation in state.get("observations", [])
        if observation.get("result") == "fail"
        or observation.get("failure_signature")
    ]
    if failures:
        for observation in failures[-3:]:
            signature = compact(
                observation.get("failure_signature") or "unlabeled"
            )
            evidence = compact(
                observation.get("evidence") or "no reference", 180
            )
            lines.append(f"- {signature} ({evidence})")
    else:
        lines.append("- none recorded")
    lines.append(
        "Next probes: "
        + compact("; ".join(state.get("next_probes", [])) or "candidate-specific")
    )
    lines.append("")
    for candidate in state.get("pending_candidates", []):
        lines.append(
            f"Candidate {candidate['id']}: "
            f"{compact(candidate['assumption'], 120)} / "
            f"probe: {compact(candidate['probe'], 120)} / "
            f"cost: {compact(candidate.get('cost') or 'unspecified', 80)} / "
            f"failure: {compact(candidate['failure_criterion'], 120)}"
        )
    lines.append("")
    lines.append("Choose: " + " / ".join(
        [candidate["id"] for candidate in state.get("pending_candidates", [])]
        + ["current route", "stop"]
    ))
    if len(lines) <= 20:
        return lines
    return lines[:19] + [lines[-1]]


def command_packet(args: argparse.Namespace) -> int:
    path = state_path(args.state)
    state = load_state(path)
    status, reasons = evaluate(state)
    if status == "WAITING_FOR_USER" and state.get("pending_candidates"):
        print("\n".join(packet_lines(state)))
        return 0
    if status not in ("ROUTE_STALE", "REPLAN_REQUIRED"):
        raise StateError(
            f"packet requires a stale route; current status is {status}"
        )
    raw_candidates = values(args.candidate)
    if len(raw_candidates) < 2:
        if status == "ROUTE_STALE":
            state["status"] = "REPLAN_REQUIRED"
            state["reasons"] = reasons or state.get("reasons", [])
            save_state(path, state)
        print_status(state)
        return 0
    candidates = [candidate_from_json(raw) for raw in raw_candidates]
    ids = [candidate["id"] for candidate in candidates]
    if len(set(ids)) != len(ids):
        raise StateError("candidate ids must be unique")
    state["pending_candidates"] = candidates
    state["approval_required"] = True
    state["status"] = "WAITING_FOR_USER"
    state["reasons"] = reasons or state.get("reasons", [])
    state["terminal"] = False
    save_state(path, state)
    print("\n".join(packet_lines(state)))
    return 0


def command_approve(args: argparse.Namespace) -> int:
    path = state_path(args.state)
    state = load_state(path)
    if state.get("status") != "WAITING_FOR_USER":
        raise StateError("approval is only available in WAITING_FOR_USER")
    if not state.get("pending_candidates"):
        raise StateError("no pending candidates")
    if not args.user_text.strip():
        raise StateError("--user-text is required for an explicit approval")
    choice = args.choice.strip()
    approval = {
        "at": now(),
        "choice": choice,
        "user_text": args.user_text or "",
        "evidence": args.evidence or "",
    }
    state["approval"] = approval
    normalized_choice = choice.lower()
    if normalized_choice in ("current", "current route"):
        state["route_history"] = (
            list(state.get("route_history", []))
            + [
                {
                    "generation": state.get("route_generation", 0),
                    "route": state.get("route", {}),
                    "decision": "continue_current",
                    "reasons": state.get("reasons", []),
                    "observations": [
                        history_observation(observation)
                        for observation in state.get("observations", [])[-3:]
                    ],
                }
            ]
        )[-MAX_ROUTE_HISTORY:]
        state["observations"] = []
        state["approval_required"] = False
        state["pending_candidates"] = []
        state["status"] = "ROUTE_HEALTHY"
        state["reasons"] = []
        state["terminal"] = False
        save_state(path, state)
        print("approved current route")
        print_status(state)
        return 0
    if normalized_choice == "stop":
        state["approval_required"] = False
        state["status"] = "WAITING_FOR_USER"
        state["reasons"] = ["user_stopped"]
        state["terminal"] = True
        save_state(path, state)
        print("task stopped by user")
        print_status(state)
        return 0

    selected = next(
        (
            candidate
            for candidate in state["pending_candidates"]
            if candidate["id"].lower() == normalized_choice
        ),
        None,
    )
    if selected is None:
        raise StateError(
            "choice must be a pending candidate id, current route, or stop"
        )

    old_route = state.get("route", {})
    state["route_history"] = (
        list(state.get("route_history", []))
        + [
            {
                "generation": state.get("route_generation", 0),
                "route": old_route,
                "reasons": state.get("reasons", []),
                "observations": [
                    history_observation(observation)
                    for observation in state.get("observations", [])[-3:]
                ],
            }
        ]
    )[-MAX_ROUTE_HISTORY:]
    state["route"] = {
        "id": selected["id"],
        "assumption": selected["assumption"],
        "probe": selected["probe"],
        "failure_criterion": selected["failure_criterion"],
    }
    state["route_generation"] = state.get("route_generation", 0) + 1
    state["observations"] = []
    state["pending_candidates"] = []
    state["approval_required"] = False
    state["status"] = "ROUTE_HEALTHY"
    state["reasons"] = []
    state["terminal"] = False
    save_state(path, state)
    print(f"approved route {selected['id']}")
    print_status(state)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Track route recovery without changing the working tree."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def state_argument(command: argparse.ArgumentParser) -> None:
        command.add_argument("--state", default=".route/state.json")

    def metadata_arguments(command: argparse.ArgumentParser) -> None:
        command.add_argument("--goal")
        command.add_argument("--acceptance", action="append", default=[])
        command.add_argument("--constraint", dest="constraints", action="append", default=[])
        command.add_argument("--route-id", default="initial")
        command.add_argument("--route-assumption", default="")
        command.add_argument("--route-probe", default="")
        command.add_argument("--failure-criterion", default="")
        command.add_argument("--verified-fact", action="append", default=[])
        command.add_argument("--unverified-assumption", action="append", default=[])
        command.add_argument("--uncertainty", action="append", default=[])
        command.add_argument("--next-probe", action="append", default=[])

    init = subparsers.add_parser("init", help="create tracking state")
    state_argument(init)
    metadata_arguments(init)
    init.add_argument("--task-class", choices=("long", "uncertain"), default="long")
    init.set_defaults(function=command_init)

    promote = subparsers.add_parser("promote", help="promote a short task")
    state_argument(promote)
    metadata_arguments(promote)
    promote.set_defaults(function=command_promote)

    record = subparsers.add_parser("record", help="record a semantic checkpoint")
    state_argument(record)
    record.add_argument("--result", choices=("pass", "fail", "unknown"), default="unknown")
    record.add_argument("--acceptance", choices=("pass", "fail", "unknown"), default="unknown")
    record.add_argument("--progress", choices=("positive", "none", "negative", "unknown"), default="unknown")
    record.add_argument("--complexity", choices=("lower", "same", "higher", "unknown"), default="unknown")
    record.add_argument("--assumption-status", choices=("verified", "unverified", "contradicted"), default="unverified")
    record.add_argument("--constraint-status", choices=("satisfied", "unknown", "violated"), default="unknown")
    record.add_argument("--failure-signature", default="")
    record.add_argument("--action-signature", default="")
    record.add_argument("--expected", default="")
    record.add_argument("--observed", default="")
    record.add_argument("--reproducibility", default="")
    record.add_argument("--checkpoint", default="")
    record.add_argument("--evidence", default="")
    record.add_argument("--route-id")
    record.add_argument("--route-generation", type=int)
    record.add_argument("--verified-fact", action="append", default=[])
    record.add_argument("--unverified-assumption", action="append", default=[])
    record.add_argument("--uncertainty", action="append", default=[])
    record.add_argument("--next-probe", action="append", default=[])
    record.set_defaults(function=command_record)

    status = subparsers.add_parser("status", help="show compact route status")
    state_argument(status)
    status.set_defaults(function=lambda args: (print_status(load_state(state_path(args.state))) or 0))

    packet = subparsers.add_parser("packet", help="prepare a user approval packet")
    state_argument(packet)
    packet.add_argument("--candidate", action="append", default=[])
    packet.set_defaults(function=command_packet)

    approve = subparsers.add_parser("approve", help="record an explicit user choice")
    state_argument(approve)
    approve.add_argument("--choice", required=True)
    approve.add_argument("--user-text", default="")
    approve.add_argument("--evidence", default="")
    approve.set_defaults(function=command_approve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.function(args))
    except StateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
