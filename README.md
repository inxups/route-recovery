# Route Recovery

[English version](README.en.md)

Route Recovery 是一个用于长程 coding 任务的 Codex skill。

它把当前实现路线视为可证伪的假设，帮助 agent：

- 识别重复失败、无验收进展和复杂度增长；
- 保存目标、约束、baseline、测试结果和失败条件；
- 丢弃过时的 assistant 叙事，只保留可验证事实；
- 在重新规划后请求用户批准，禁止 agent 擅自切换路线；
- 通过紧凑状态文件跨上下文保存路线记忆。

## 状态

~~~text
ROUTE_HEALTHY
ROUTE_STALE
REPLAN_REQUIRED
WAITING_FOR_USER
DONE
~~~

长任务或不确定任务在第一次修改前建立状态；短任务在出现失败、范围扩大或需要交接时升级。路线停滞后，agent 整理至少两个候选路线并询问用户；用户批准前只能进行只读分析和当前路线验证。

运行时状态位于 .route/state.json，不会提交到 Git。

## 关键文件

- [SKILL.md](SKILL.md)：skill 的路线检测、状态管理和用户审批规则。
- [scripts/route_check.py](scripts/route_check.py)：状态和审批门控的实现。
- [scripts/test_route_check.py](scripts/test_route_check.py)：状态转换和审批流程测试。
- [.gitignore](.gitignore)：忽略运行时状态和本地缓存。
