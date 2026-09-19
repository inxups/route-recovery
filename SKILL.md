---
name: route-recovery
description: Recover stalled coding tasks by preserving verified facts and testing a new route when the current plan stops making progress.
---

# Route Recovery

Use this skill for coding tasks that may span multiple edits, modules, validations, or contexts.

## Non-negotiable rules

1. Keep the user goal and constraints stable.
2. Treat the current route as a falsifiable hypothesis.
3. When evidence shows a route problem, stop before the next edit.
4. Preserve verified facts; discard stale explanations and guesses.
5. Never switch routes without the user explicit choice.
6. Never auto-reset, clean, delete, install dependencies, migrate, or rewrite broadly.

## 1. Classify the task

Classify before the first code edit.

**Short task**: one local module, one clear acceptance surface, no architecture/data-model/migration/external-system/unknown-API risk, and one bounded change is likely enough.

**Long or uncertain task**: any other case. Default to this class when uncertain.

For a long or uncertain task, create `.route/state.json` before editing. Record:

- goal
- acceptance criteria
- constraints
- baseline
- initial route assumption
- first probe
- failure criterion

Promote a short task before its next edit when any of these occurs:

- the first verification fails and another fix is planned;
- the scope expands or a second acceptance surface appears;
- a route assumption changes;
- work must cross contexts;
- architecture, dependency, or external-system uncertainty appears.

On promotion, set `history_before_tracking: unknown`. Do not invent earlier observations.

## 2. Record semantic checkpoints

Do not log every command. Record only route selection, probes/tests/builds/acceptance checks, bounded fixes, assumption changes, route decisions, route switches, and context handoffs.

Each observation contains:

- result: `pass`, `fail`, or `unknown`
- progress: `positive`, `none`, `negative`, or `unknown`
- complexity: `lower`, `same`, `higher`, or `unknown`
- assumption: `verified`, `unverified`, or `contradicted`
- failure signature, checkpoint, and evidence reference when applicable

Keep only the latest three or four observations in state. Store long output by path, command, or Git reference. Never copy raw logs or the full conversation into state.

## 3. Handle a problem

When a problem appears, stop before editing again. Record:

- expected result
- observed result
- normalized `failure_signature`
- reproducibility
- affected assumption
- checkpoint
- evidence

Then classify it:

- Environment or flaky failure: retry once under the same conditions.
- Local implementation defect: allow one bounded fix if the core assumption, interface, and architecture remain unchanged.
- Insufficient evidence: run the smallest discriminating probe.
- Contradicted core assumption or hard constraint: freeze the route immediately.
- Growing complexity without progress: freeze the route.

These actions remain on the current route: local fixes, rerunning existing checks, read-only inspection, and undoing the most recent bounded change when safe. Changing architecture, data model, API, dependency, interface contract, migration, checkpoint family, or rewrite scope is a route switch.

## 4. Detect route trouble

Set `ROUTE_STALE` when any trigger is met across controlled checkpoints:

- the same `failure_signature` appears twice;
- two checkpoints show no acceptance progress;
- scope or complexity increases without a new verified prediction;
- the same action, patch, command, or explanation repeats without new evidence.

A single flaky failure, no-progress checkpoint, or complexity increase is insufficient.

Set `REPLAN_REQUIRED` when the stale route needs a different core assumption. Use reason codes:

- `constraint_violation`
- `assumption_falsified`
- `repeated_failure`
- `no_progress`
- `complexity_growth`
- `alternative_dominates`

Use `alternative_dominates` only when a candidate passes the same acceptance checks, adds no regression, and has lower measured change, complexity, risk, or rollback cost. Do not claim global optimality.

## 5. Freeze, replan, and ask

Before route analysis, preserve the current state and a recoverable checkpoint. Do not discard user changes.

Generate a compact packet:

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

Prepare at least two materially different candidates. For each, state its core assumption, smallest discriminating probe, expected cost, and failure criterion. Read-only inspection or probing is allowed; candidate implementation and route-specific changes require approval.

After candidates are ready, set `WAITING_FOR_USER` and pause route changes. Ask:

```text
Current route:
Triggering evidence:
Verified facts:
Unverified assumptions:

Candidate A: assumption / probe / cost / failure criterion
Candidate B: assumption / probe / cost / failure criterion

Choose: A / B / current route / stop
```

The agent may recommend a choice but must not treat its recommendation as authorization. Record the user exact choice before changing `route_generation`. No reply means remain waiting.

## 6. Execute an approved route

After approval:

1. Record the user original choice.
2. Increment `route_generation`.
3. Keep the old route and evidence.
4. Create a checkpoint for the new route.
5. Start with its smallest probe.

Use the loop `one hypothesis -> one bounded change -> one verification`.

A context handoff is not a route switch. Reuse the packet when the route is unchanged. If the same stop signal appears again after a replan, stop blind repair and report the evidence and the next user decision.

## 7. State and tool boundary

Runtime state is `.route/state.json`; it must remain ignored by Git. Valid statuses are:

`ROUTE_HEALTHY`, `ROUTE_STALE`, `REPLAN_REQUIRED`, `WAITING_FOR_USER`, `DONE`.

Use `scripts/route_check.py` for state operations:

- `init`: create long-task state;
- `promote`: upgrade a short task;
- `record`: append a semantic observation;
- `status`: calculate status and reason;
- `packet`: create the compact replan packet and enter waiting;
- `approve`: record an explicit user choice.

The script only changes the state file, uses Python standard library, never guesses test commands, and never changes business code or Git history. Do not call `approve` without the user actual choice. `current` means explicitly continue the frozen route; `stop` means end the task.
