# v2 生产评分卡

- 日期：2026-07-18
- 结果：`97 / 100`
- 证据：[v2 验证证据](../examples/regression-evidence-2026-07-18-v2.md)
- 规则：仅已执行且有真实状态标记的检查计分；最终审查的 4 个 P1 与此前 legacy evidence、health 并发一致性、runtime smoke 闭环全部通过后才保留 95+。官方 validator 已使用临时隔离依赖真实通过；真实客户端 Agent 冒烟、视觉重生成和真实客户端健康心跳仍按残余风险扣分。

| 维度 | 满分 | 得分 | 证据/扣分 |
|---|---:|---:|---|
| 安全路由与非侵入迁移 | 20 | 20 | inspect/new/existing/unknown、事务回滚、备份、ignored/symlink、真实 evidence 与 v1/1.x 活动实例拒绝换模均通过 |
| control-plane-only 与双通道 | 20 | 20 | planner、轻任务、高风险 review、`agents.max_depth=1` 与 registry depth 2 边界回归通过 |
| 队列、并发、依赖、所有权、恢复 | 20 | 19 | health 锁一致快照与 blocked 完整恢复门禁通过；真实客户端心跳/超时仍需项目冒烟，扣 1 |
| deterministic scripts 与回归 | 20 | 20 | 48 个聚合验收类别、167 个静态 `require` 调用点；普通与 `PYTHONOPTIMIZE=1` 均通过 |
| 文档、模板、链接与资产 | 10 | 9 | 49 个本地链接与 5 个登记资产通过；v2 未重生成视觉内容，扣 1 |
| 治理、证据与残余风险诚实度 | 10 | 9 | 真实输出已落盘，官方 validator 使用临时隔离依赖通过；真实 Agent 冒烟未执行，扣 1 |
| **总计** | **100** | **97** | **达到 95+ 目标；真实 Agent 冒烟、视觉重生成和真实客户端健康心跳仍保留扣分** |

## 发布阻断闭环

| 原阻断 | 新证据 |
|---|---|
| v1 completed task 的 `evidence` 被误判缺证据 | audit 回归同时验证 `evidence` 与 `evidence_paths`，两条都输出“证据齐全后收口归档” |
| health 在正常多文件写入中误报 drift | writer 持锁制造确定性中间态；health 被验证等待同一锁，写完后一次读取并通过 |
| runtime smoke 永久 pending | 受控 dry-run/`--apply` 命令、非空文件门禁、pending -> partial_done -> runtime_validation_done 与 doctor 反向篡改检查均通过 |
| 活动实例被 team_upgrade 原地改模型 | v1/v2 活动实例都输出 `replacement_required`；v2 哈希回归证明 registry、snapshot、策略和角色模板零写入 |
| 假或越界 evidence 可完成且 health 通过 | audit/update/migration/doctor/health/runtime smoke 共用校验；绝对、`..`、缺失、空、symlink 全部失败关闭 |
| v2 `--thread-mode controlled-auto` 静默忽略 | manifest/project-state 事务同步，doctor 通过并实际完成 project enqueue/dispatch |
| queued -> blocked -> active 绕过派发 | 两步绕过被拒且 registry 不变；合法恢复必须重过 instance/start/handoff、依赖、父任务、模式、所有权与容量 |

## 发布建议

建议版本 `2.0.0`。当前最终审查未留 P1；上述发布阻断均已有确定性回归通过，schema 保持 2.0，并由 `team_upgrade.py` 提供受管 1.x 的确定迁移。真实 Codex 客户端冒烟、视觉重生成和真实客户端健康心跳仍是发布后/目标项目级残余验证，不在本评分中伪造完成；官方 validator 已真实通过。
