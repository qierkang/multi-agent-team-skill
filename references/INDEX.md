# References 索引

按 inspect 结果和当前动作渐进读取，禁止一次性预热全部文件。

| 文件 | 何时读取 |
|---|---|
| [workflow-new-team.md](workflow-new-team.md) | `new` 初始化 |
| [workflow-existing-project.md](workflow-existing-project.md) | `existing-project` 非侵入安装 |
| [workflow-existing-team.md](workflow-existing-team.md) | 未知、自定义或非受管团队审计 |
| [schema-migration.md](schema-migration.md) | `existing-team:v1` / `v2-upgrade` |
| [runtime-orchestration.md](runtime-orchestration.md) | fast/project 规划、队列、派发、依赖、替换 |
| [coordination-contract.md](coordination-contract.md) | 控制面、派发包、所有权、审查协议 |
| [long-thread-policy.md](long-thread-policy.md) | project lane 创建/复用与层级限制 |
| [health-anomaly-token.md](health-anomaly-token.md) | 心跳、超时、失败两次升级和 Token |
| [state-model.md](state-model.md) | 状态机与受管文件 |
| [thread-snapshot-schema.md](thread-snapshot-schema.md) | registry 与状态快照字段 |
| [role-selection.md](role-selection.md) | Luna/Terra/Sol 与角色选择 |
| [migration-rules.md](migration-rules.md) | 未知团队迁移计划与人工边界 |
| [completion-gate.md](completion-gate.md) | 声明完成前 |
| [github-publish.md](github-publish.md) | 仅在用户明确要求发布时 |

固定阅读顺序：`SKILL.md -> inspect 输出 -> 对应 workflow -> 当前动作 reference -> scripts/templates`。
