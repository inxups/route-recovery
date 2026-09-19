# Route Recovery

[中文说明](README.md)

Route Recovery is a Codex skill for long-running coding tasks.

It treats the current implementation route as a falsifiable hypothesis and helps an agent:

- detect repeated failures, missing acceptance progress, and growing complexity;
- preserve the goal, constraints, baseline, test results, and failure conditions;
- discard stale assistant narrative while retaining verified facts;
- ask the user before switching routes after replanning;
- carry compact route state across context changes.

## Statuses

~~~text
ROUTE_HEALTHY
ROUTE_STALE
REPLAN_REQUIRED
WAITING_FOR_USER
DONE
~~~

Long or uncertain tasks create state before the first edit. Short tasks are promoted when a verification fails, scope expands, or a context handoff is needed. When a route becomes stale, the agent prepares at least two candidates and asks the user; before approval it may only inspect read-only evidence and verify the current route.

Runtime state lives in .route/state.json and is not committed to Git.

## Key Files

- [SKILL.md](SKILL.md): route detection, state management, and user approval rules.
- [scripts/route_check.py](scripts/route_check.py): state and approval gate implementation.
- [scripts/test_route_check.py](scripts/test_route_check.py): state transition and approval flow tests.
- [.gitignore](.gitignore): ignores runtime state and local caches.
