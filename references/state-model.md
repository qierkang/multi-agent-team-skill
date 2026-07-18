# v2 状态模型

任务状态：`queued -> active -> waiting_input/reviewing/degraded -> completed/blocked/cancelled -> archived`。同因失败两次进入 `escalation_required`，由新实例 `replace` 后回到 active；Sol 无升级档时 blocked。blocked 恢复 active 必须已有 dispatch instance/start/handoff，并重新通过依赖、父任务、模式、domain、所有权和容量门禁；从未 dispatch 的 blocked 队列项不能恢复 active。

| 文件 | 真源 |
|---|---|
| `.codex/team/project-state.json` | 控制面、lane、容量、模型、超时、Token 策略 |
| `.codex/team/thread-registry.json` | 队列与运行任务、依赖、层级、实例、handoff |
| `.codex/team/ownership-locks.json` | 活跃任务派生路径锁 |
| `.codex/team/budget-state.json` | 派生 Token 状态 |
| `.codex/team/recovery-journal.json` | 迁移、失败、替换和恢复事件 |
| `docs/协作/状态快照.json` | 与 registry 同步的人读快照 |
| `.codex/team-bootstrap.json` 的 `runtime_smoke_*` | 客户端冒烟 `pending / partial_done / runtime_validation_done` 与 explorer/reviewer 证据 |

registry mutation 使用进程锁、revision CAS 和原子替换；health 在同一进程锁下读取 registry、锁、预算和快照，避免观察到写入中间态。聊天不是唯一状态真源。

`runtime_smoke.py` 默认 dry-run。只记录项目内已存在、非空、非 symlink 的真实客户端日志；单侧角色证据只能到 `partial_done`，explorer 与 fresh reviewer 两侧齐全才到 `runtime_validation_done`。无法运行客户端时保持 `pending`。
