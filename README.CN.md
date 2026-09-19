# Route Recovery

[English version](README.md)

Route Recovery 是一个用于长程 coding 任务的 skill。

```bash
npm i route-recovery
```


此Skill把当前实现路线视为可证伪的假设，帮助 agent：
- 识别重复失败、无验收进展和复杂度增长；
- 保存目标、约束、baseline、测试结果和失败条件；
- 丢弃过时的 assistant 叙事，只保留可验证事实；
- 在重新规划后请求用户批准，禁止 agent 擅自切换路线；
- 通过紧凑状态文件跨上下文保存路线记忆。

长任务或不确定任务在第一次修改前建立状态；短任务在出现失败、范围扩大或需要交接时升级。路线停滞后，agent 整理至少两个候选路线并询问用户；用户批准前只能进行只读分析和当前路线验证。

### 状态
~~~text
ROUTE_HEALTHY
ROUTE_STALE
REPLAN_REQUIRED
WAITING_FOR_USER
DONE
~~~

### 来源
我在长程任务中使用非顶级模型时，面对困难或非常规任务，常常需要我手动去纠正模型路线，这非常痛苦，由此而生。
