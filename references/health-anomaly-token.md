# 健康、异常、超时与 Token

`thread_orchestrator.py health` 检查：schema、control-plane-only、总并发 6、写并发 2、domain、依赖、层级、instance ID、所有权、心跳、超时、模型、证据、Token 和派生状态漂移。

## 异常处置

1. 第一次同因失败：记录 fingerprint、现场和 handoff，允许同实例一次受控重试。
2. 第二次同因失败：状态转 `escalation_required`，旧实例不换脑且释放槽位。
3. `replace` 必须使用新 instance ID、保存的 handoff 和下一档模型。
4. Sol 无更高档位时阻塞并请求决策；禁止盲目重试。
5. stale heartbeat 或 timeout 不等同完成；先保存现场，再决定恢复或替换。

## Token

- 70%：压缩上下文，只保留摘要、决策和证据索引。
- 85%：冻结扩展范围，只完成当前验收。
- 100%：保存 handoff 并停止。

派生锁、预算或状态快照漂移先 dry-run `reconcile`，确认后 `--apply`。外部动作仍需独立明确批准。
