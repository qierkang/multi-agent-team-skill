# References 索引

按需加载，禁止一次性预热全部文件。

| 文件 | 何时读取 |
|---|---|
| [workflow-new-team.md](workflow-new-team.md) | 空目录或全新项目初始化时 |
| [workflow-existing-project.md](workflow-existing-project.md) | 已有业务代码、尚未部署团队时 |
| [workflow-existing-team.md](workflow-existing-team.md) | 已有角色、配置、清单或常驻任务时 |
| [migration-rules.md](migration-rules.md) | 生成或执行已有团队迁移方案时 |
| [thread-snapshot-schema.md](thread-snapshot-schema.md) | 导出任务状态用于团队审计时 |
| [role-selection.md](role-selection.md) | 决定角色数量、档案和推理档位时 |
| [coordination-contract.md](coordination-contract.md) | 生成 AGENTS 规则、台账或任务包时 |
| [state-model.md](state-model.md) | 解释机读状态或编排下一步时 |
| [completion-gate.md](completion-gate.md) | 准备声明初始化完成前必读 |
| [runtime-orchestration.md](runtime-orchestration.md) | 评分、创建/复用长期任务和登记客户端 ID 时 |
| [long-thread-policy.md](long-thread-policy.md) | 决定是否创建长期任务、模型与所有权时 |
| [health-anomaly-token.md](health-anomaly-token.md) | 心跳、冲突、失败、Token 和恢复处置时 |
| [schema-migration.md](schema-migration.md) | 受管 v1 -> v2 升级或未知 schema 拦截时 |

构造 `thread_orchestrator.py plan` 的任务 JSON 前，先看 `runtime-orchestration.md` 的“任务输入字段表”和 `examples/task-input.example.json`，字段名以该表为准。

读取顺序：`SKILL.md -> workflow -> 相关规则 -> scripts -> templates`。静态图片等展示资产才读取 `assets/`。
