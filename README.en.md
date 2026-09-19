# Route Recovery

[中文说明](README.md)

Route Recovery is a skill for long-running coding tasks.

This skill treats the current implementation route as a falsifiable hypothesis and helps the agent:

- detect repeated failures, missing acceptance progress, and growing complexity;
- preserve goals, constraints, baselines, test results, and failure conditions;
- discard stale assistant narrative while retaining verified facts;
- ask the user before switching routes after replanning;
- carry compact route state across context changes.

Long or uncertain tasks create state before the first edit. Short tasks are promoted when a verification fails, scope expands, or a context handoff is needed. When a route becomes stale, the agent prepares at least two candidate routes and asks the user; before approval, it may only inspect read-only evidence and verify the current route.

### Status

~~~text
ROUTE_HEALTHY
ROUTE_STALE
REPLAN_REQUIRED
WAITING_FOR_USER
DONE
~~~

### Origin

When I work on long-running, difficult, or unconventional tasks with a non-frontier model, I often have to manually correct the model's route. This skill grew out of that frustration.
