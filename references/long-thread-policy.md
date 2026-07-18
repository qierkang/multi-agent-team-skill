# Project Lane 长期任务策略

任务评分达到 7 才进入 project lane：跨日 +2、至少三个任务包 +2、独立边界 +2、持续维护 +2、独立发布/决策保留/可并行各 +1。

- `recommend` 默认只推荐；`controlled-auto` 才允许控制面调用客户端创建。
- 相同 `domain_key` 复用一个活跃长期任务。
- 活跃容量不足时任务继续排队；队列本身不限数量。
- 长期任务可向主控制面申请一次性 Agent，但自身不得递归创建 Agent 或长期任务；Codex `agents.max_depth=1`，registry 受管层级最多为 2。
- 每个写任务持有互斥项目相对路径，终态释放。
- 运行中不换 Luna/Terra/Sol；升级必须保存 handoff、关闭旧实例并创建新实例。
- 高风险阶段结束使用全新 reviewer，不复用长期 reviewer。
