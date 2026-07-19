# v2 运行时编排契约

## 控制面

主任务默认 `control-plane-only`：可以只读判断、拆分、排队、派发、监控、验收、汇报和写受管调度状态，但不得修改生产代码。planner 永不返回“主任务直接实现”。

所有写任务必须绑定 inspect 已确认项目根目录内的相对 `owned_paths`；发现目标是另一 checkout/worktree 或根目录之外路径时停止并重新 inspect，不得跨工作区直接修改。

### Dispatch-and-return

成功 spawn 一个或一批 Agent 后，主任务必须立即 ACK 任务编号、角色、状态并结束当前 turn；多个独立 Agent 必须先批量 spawn，再一次性 ACK。该 turn 禁止 `wait_agent`、重复 read/status polling、长测试或继续集成。完成通知、health、验收和重派只在后续用户 turn、完成事件 turn 或自动化唤醒处理；用户新消息优先，由依赖队列和路径所有权避免冲突。同步等待仅在用户明确要求并先告知会阻塞输入时允许。Python 无法控制客户端 turn 结束，不得伪造 UI 并发证据。

## 任务输入字段

| 字段 | 类型 | 必填 | 约束 |
|---|---|---:|---|
| `domain_key` | string | 是 | 非空；project lane 活跃时唯一 |
| `title` | string | 是 | 非空 |
| `owned_paths` | string[] | 否 | 项目相对路径，禁止绝对路径和 `..` |
| `expected_days` | number | 否 | 非负有限数；`>1` 记 +2 |
| `task_packages` | integer | 否 | 非负；`>=3` 记 +2 |
| `independent_boundary` | boolean | 否 | +2 |
| `recurring` | boolean | 否 | +2 |
| `independent_release` | boolean | 否 | +1 |
| `decision_retention` | boolean | 否 | +1 |
| `parallelizable` | boolean | 否 | +1 |
| `task_type` | enum | 否 | implementation/exploration/chore/docs/research/architecture/security/review/migration |
| `risk` | enum | 否 | low/medium/high/critical |
| `attempts` | integer | 否 | 非负 |
| `dependencies` | string[] | 否 | 必须指向已登记任务，禁止循环 |
| `parent_thread_id` | string | 否 | 仅 project lane 活跃任务可作为父任务 |
| `timeout_seconds` | integer | 否 | 正整数 |

未知字段失败关闭。示例见 `examples/task-input.example.json`。

## Lane 与派发策略

评分达到 7 进入 project lane，否则进入 fast lane。轻任务是 low risk、预计不超过 0.5 天、最多一个任务包、无独立发布和长期决策保留的 fast 任务。

| 结果 | 控制面动作 |
|---|---|
| `dispatch_fast_agent` | 派一次性 Agent；轻任务 minimal packet + on-failure review |
| `create_project_thread` | controlled-auto 下入队并创建长期任务，再绑定客户端 ID |
| `recommend_project_thread` | recommend 模式只推荐，不创建 |
| `reuse_project_thread` | 按 registry 的同 `domain_key` 活跃长期任务复用 |
| `queue_*_capacity` | 总并发 6 已满，保持排队 |
| `queue_*_writer` | 写并发 2 已满，保持排队 |
| `queue_*_ownership` | 路径祖先/子路径冲突，保持排队 |

队列数量不限。高/critical 风险的 `review_policy` 始终为 `always-fresh-reviewer`。

## 状态与命令

`queued -> active -> waiting_input/reviewing/degraded -> completed/blocked/cancelled -> archived`

同因失败两次进入 `escalation_required`；Sol 无更高档位时进入 `blocked`。
`blocked -> active` 不是通用旁路：必须已有真实 dispatch instance/start metadata，提供存在且非空的 handoff，并重新通过依赖、父任务、controlled-auto、domain、所有权、总并发和写并发门禁。从未 dispatch 的 `queued -> blocked` 任务不得恢复为 active。

```bash
python3 scripts/thread_orchestrator.py plan --project <path> --task-json task.json
python3 scripts/thread_orchestrator.py enqueue --project <path> --task-json task.json --task-id TASK-001 --apply
python3 scripts/thread_orchestrator.py dispatch --project <path> --task-id TASK-001 --instance-id <id> --apply
python3 scripts/thread_orchestrator.py update --project <path> --thread-id TASK-001 --stage verified --evidence artifacts/test.log --apply
python3 scripts/thread_orchestrator.py fail --project <path> --task-id TASK-001 --fingerprint same-cause --handoff artifacts/handoff.md --apply
python3 scripts/thread_orchestrator.py replace --project <path> --task-id TASK-001 --new-instance-id <new-id> --new-model <required-model> --handoff artifacts/handoff.md --apply
```

除只读 `plan`/`health` 外，状态命令默认 dry-run，写入需 `--apply`。`register` 保留为旧客户端直接登记 project task 的兼容入口。

## 并发、层级和完成

- 活跃执行总数最多 6；写实例最多 2。
- Codex 项目配置保持 `agents.max_depth=1`，禁止任何 Agent 自行递归创建 Agent。
- registry 中 main -> fast 为 depth 1；main -> project -> one-shot 为受管 depth 2。depth 2 的 one-shot 由主控制面代 project task 创建/绑定，不代表把 Codex `max_depth` 设为 2。
- dispatch 前依赖必须 completed，所有权和容量必须可用。
- 运行中不改模型；replace 必须使用新 instance ID 和 planner 要求的更高档模型。
- completed 的每个证据路径必须是项目相对、无 `..`、已存在、非空、非 symlink 的普通文件；audit、update、migration、doctor、health 与 runtime smoke 使用同一校验口径。终态自动释放活跃锁。


## Goal boundary
- `goal_policy=explicit-only`; `control_plane_is_goal=false`; project control defaults to `controlled-auto`.
- A project task/long-lived domain task is not a Codex Goal. An active Goal reports `GOAL_MODE=unsupported_for_control_plane_setup` and is never reused or created by this Skill.
