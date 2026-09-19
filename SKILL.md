---
name: route-recovery
description: Recover stalled coding tasks by preserving verified facts and testing a new route when the current plan stops making progress.
---

# Route Recovery

Treat the current implementation route as a falsifiable hypothesis. Keep the task goal stable, preserve verified facts, and do not let stale assistant narrative decide what happens next.

## Task lifecycle

Classify the task before the first code change.

- Treat a task as short only when it is local, has one clear acceptance surface, has no architectural, migration, external-system, or unknown-API risk, and should need one bounded change.
- Treat it as long or uncertain when any of those conditions is false. For a long or uncertain task, create `.route/state.json` before the first code change with the goal, acceptance criteria, constraints, Git baseline, initial route assumption, first probe, and failure criterion.
- A short task is promoted before the next edit if its first verification fails and another fix is planned, the scope expands, a second acceptance surface appears, a route assumption changes, or context must be handed off. Mark pre-promotion history as unknown; do not invent it.

Use `scripts/route_check.py` to create and update state. Do not create a full log for every shell command. Record semantic checkpoints: route selection, probes/tests/builds, bounded changes, assumption changes, route decisions, and context handoffs.

## Detect and classify

When a problem appears, stop before the next code edit and record the expected result, observed result, normalized failure signature, reproducibility, affected assumption, checkpoint, and evidence reference.

- Retry an environment or flaky failure once under the same conditions.
- A local defect may receive one bounded fix only if the core assumption, interface, and architecture stay unchanged.
- For uncertain evidence, run the smallest discriminating probe.
- A hard-constraint conflict or contradicted core assumption freezes the route immediately.

Mark the route stale when any of these persists across controlled checkpoints:

- the same failure signature appears twice;
- two checkpoints have no measurable acceptance progress;
- complexity or scope grows without a new verified prediction;
- the same action is repeated without new evidence.

One flaky failure, one no-progress checkpoint, or one complexity increase is not enough by itself.

## Freeze and replan

Before changing direction, preserve the current state and a recoverable Git checkpoint. Do not reset, clean, overwrite, discard user changes, or perform a broad patch series.

Generate a compact replan packet containing:

```text
Goal:
Acceptance criteria:
Constraints:
Baseline:
Verified facts:
Failed routes and evidence:
Unverified assumptions:
Open uncertainties:
Next probes:
```

Use a fresh context when available. Require at least two materially different candidate routes, each with a core assumption, smallest discriminating probe, failure criterion, and checkpoint. A candidate may be inspected or tested read-only, but its implementation, dependency changes, interface changes, migrations, architecture changes, large rewrites, or route-specific rollback require user approval.

## User approval gate

Use these statuses:

```text
ROUTE_HEALTHY
ROUTE_STALE
REPLAN_REQUIRED
WAITING_FOR_USER
DONE
```

After candidates are prepared, enter `WAITING_FOR_USER`. Do not choose or implement a new route automatically. Ask the user to choose a candidate, continue the current route, or stop. Record the user's explicit choice with `route_check.py approve` before changing the route generation. No answer means no route change.

The approval request should stay compact:

```text
Current route:
Triggering evidence:
Verified facts:
Unverified assumptions:

Candidate A: assumption / probe / cost / failure criterion
Candidate B: assumption / probe / cost / failure criterion

Choose: A / B / current route / stop
```

Do not call a route globally optimal. Use `alternative_dominates` only when an alternative has passed the same acceptance checks with lower measured change, complexity, risk, or rollback cost.

## Execute with checkpoints

For an approved route, use:

```text
one hypothesis -> one bounded change -> one verification
```

Keep only the latest three or four observations in state. Store paths or Git references to long output instead of copying it into context. A context handoff is not a route change; reuse the packet if the route is unchanged.

If the same stop signal returns after a replan, stop expanding the patch and report the evidence and the next decision needed.

## State and safety

The project-local `.route/state.json` is runtime state and must remain ignored by Git. The state contains the task class, goal, acceptance criteria, constraints, baseline, current route, recent observations, route generation, pending candidates, approval record, and current status.

`route_check.py` is standard-library-only. It may write the state file, but it never resets Git, cleans files, creates branches, rolls back code, installs dependencies, or guesses test commands.

Use the CLI contract below; call `status` at a semantic checkpoint and call `packet` only after a stale route has produced at least two candidates:

```text
python scripts/route_check.py init --state .route/state.json --goal "..." --acceptance "..." --route-assumption "..." --route-probe "..." --failure-criterion "..."
python scripts/route_check.py promote --state .route/state.json --goal "..."
python scripts/route_check.py record --state .route/state.json --result fail --progress none --failure-signature "..." --checkpoint "..." --evidence "..."
python scripts/route_check.py status --state .route/state.json
python scripts/route_check.py packet --state .route/state.json --candidate '{"id":"A","assumption":"...","probe":"...","failure_criterion":"..."}' --candidate '{"id":"B","assumption":"...","probe":"...","failure_criterion":"..."}'
python scripts/route_check.py approve --state .route/state.json --choice A --user-text "User selected A"
```

Never use `approve` without the user's actual route choice. Use `--choice current` only for an explicit decision to continue the frozen route, and `--choice stop` to end the task.

Use these reason codes when a caller needs detail:

```text
constraint_violation
assumption_falsified
repeated_failure
no_progress
complexity_growth
alternative_dominates
```
