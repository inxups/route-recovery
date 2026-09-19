# Route Recovery

## 中文

Route Recovery 是一个用于长程 coding 任务的 Codex skill。

它把当前实现路线视为可证伪的假设，帮助 agent：

- 识别重复失败、无验收进展和复杂度增长；
- 保存目标、约束、baseline、测试结果和失败条件；
- 丢弃过时的 assistant 叙事，只保留可验证事实；
- 通过紧凑状态文件跨上下文保存路线记忆；
- 在重新规划后要求用户批准，禁止 agent 擅自切换路线；
- 用“一个假设 -> 一个有限修改 -> 一次验证”推进工作。

### 状态

~~~text
ROUTE_HEALTHY
ROUTE_STALE
REPLAN_REQUIRED
WAITING_FOR_USER
DONE
~~~

运行时状态默认写入项目目录的 .route/state.json，不会进入 Git 提交。

### 使用

长任务在第一次代码修改前初始化状态：

~~~bash
python scripts/route_check.py init \
  --state .route/state.json \
  --goal "..." \
  --acceptance "..." \
  --route-assumption "..." \
  --route-probe "..." \
  --failure-criterion "..."
~~~

短任务在变复杂时升级：

~~~bash
python scripts/route_check.py promote \
  --state .route/state.json \
  --goal "..."
~~~

在语义 checkpoint 记录观察：

~~~bash
python scripts/route_check.py record \
  --state .route/state.json \
  --result fail \
  --progress none \
  --failure-signature "..." \
  --checkpoint "..." \
  --evidence "..."
~~~

检查状态：

~~~bash
python scripts/route_check.py status --state .route/state.json
~~~

路线停滞后，准备至少两个候选路线。候选路线可以只读分析，但实现新路线前必须询问用户：

~~~bash
python scripts/route_check.py packet \
  --state .route/state.json \
  --candidate '{"id":"A","assumption":"...","probe":"...","failure_criterion":"..."}' \
  --candidate '{"id":"B","assumption":"...","probe":"...","failure_criterion":"..."}'
~~~

只有用户明确选择后才能继续：

~~~bash
python scripts/route_check.py approve \
  --state .route/state.json \
  --choice A \
  --user-text "User selected A"
~~~

### 测试

~~~bash
python3 -m unittest scripts/test_route_check.py
~~~

脚本只使用 Python 标准库，不会自动 reset、clean、rollback、创建分支或安装依赖。

## English

Route Recovery is a Codex skill for long-running coding tasks.

It treats the current implementation route as a falsifiable hypothesis and helps an agent:

- detect repeated failures, missing acceptance progress, and growing complexity;
- preserve the goal, constraints, baseline, test results, and failure conditions;
- discard stale assistant narrative while retaining verified facts;
- carry compact route state across context changes;
- require user approval after replanning instead of switching routes autonomously;
- work in the loop: one hypothesis -> one bounded change -> one verification.

### Statuses

~~~text
ROUTE_HEALTHY
ROUTE_STALE
REPLAN_REQUIRED
WAITING_FOR_USER
DONE
~~~

Runtime state is stored in .route/state.json and is ignored by Git.

### Usage

Initialize state before the first code change for a long task:

~~~bash
python scripts/route_check.py init \
  --state .route/state.json \
  --goal "..." \
  --acceptance "..." \
  --route-assumption "..." \
  --route-probe "..." \
  --failure-criterion "..."
~~~

Promote a short task when its scope or uncertainty grows:

~~~bash
python scripts/route_check.py promote \
  --state .route/state.json \
  --goal "..."
~~~

Record an observation at a semantic checkpoint:

~~~bash
python scripts/route_check.py record \
  --state .route/state.json \
  --result fail \
  --progress none \
  --failure-signature "..." \
  --checkpoint "..." \
  --evidence "..."
~~~

Inspect the route status:

~~~bash
python scripts/route_check.py status --state .route/state.json
~~~

When a route is stale, prepare at least two candidates. Candidates may be inspected read-only, but implementing a new route requires user approval:

~~~bash
python scripts/route_check.py packet \
  --state .route/state.json \
  --candidate '{"id":"A","assumption":"...","probe":"...","failure_criterion":"..."}' \
  --candidate '{"id":"B","assumption":"...","probe":"...","failure_criterion":"..."}'
~~~

Continue only after an explicit user choice:

~~~bash
python scripts/route_check.py approve \
  --state .route/state.json \
  --choice A \
  --user-text "User selected A"
~~~

### Tests

~~~bash
python3 -m unittest scripts/test_route_check.py
~~~

The scripts use only the Python standard library. They never automatically reset, clean, roll back, create branches, or install dependencies.
