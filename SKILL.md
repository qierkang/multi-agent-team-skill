---
name: multi-agent-team
description: 用户要求用 multi-agent-team-skill 初始化、升级、检查项目，或需要受控多 Agent 并行、长期领域任务、队列、心跳、Token 与失败恢复时触发。普通单文件修改和纯咨询不触发。
metadata:
  version: "2.0.4"
---
# Multi-Agent Team v2.0.4
主任务默认是唯一 `control-plane-only` 控制面：只做只读判断、拆分、派发、监控、验收、汇报和受管调度状态写入，不写生产代码。
用户给出项目路径后，无需询问 orchestrator 等内部术语，必须先执行：
```bash
python3 scripts/inspect_team.py --project <项目根目录>
```
inspect-first 同时按 README 第一处有效 H1、可读 project/package manifest、目录名确定显示名，输出 `主控｜<项目显示名>`。路由成功后主控必须调用 `codex_app__set_thread_title`（当前任务可省略 `threadId`）；脚本只输出 `RENAME_ACTION` 建议，不能伪造成功。客户端不支持时继续安装/健康检查并明确 `TITLE_RENAME=pending`。

| inspect 结果 | 动作 |
|---|---|
| `new` / `existing-project` | 读对应 workflow，dry-run `team_init.py` |
| `existing-team:v1` / `v2-upgrade` | 读 `schema-migration.md`，dry-run `team_upgrade.py` |
| `existing-team:audit` | 运行只读 `team_audit.py`，未知 schema 失败关闭 |
| `existing-team:v2` | 运行 `team_doctor.py` 与 orchestrator `health`；AGENTS 非受管区冲突必须失败关闭 |

用户明确要求“升级并开启受控自动”时，可用 `team_upgrade.py --thread-mode controlled-auto`；指定当前主控后，客户端真实重命名/置顶成功，再用 `bind_control_task.py` 持久化绑定。
## Goal 隔离（硬约束）
“主控任务/主控线程/项目主控/当前对话设为项目主控”均是普通 Codex 对话控制面，绝不等价于 Goal；project state 固定 `goal_policy=explicit-only`、`control_plane_is_goal=false`，默认 `controlled-auto`。除非用户明确要求创建 Goal、使用目标模式或设置目标预算，否则不调用 Goal、goal-writer 或 `/goal`。初始化/升级措辞即无冲突 dry-run 后 apply 授权，无需二次确认。

若当前线程已有 Goal，报告 `GOAL_MODE=unsupported_for_control_plane_setup`，建议普通新线程；不复用、新建、完成或删除已有 Goal。project task/长期领域任务不是 Codex Goal。静态 Skill 无法从代码层绝对阻止客户端违规，只能依赖 AGENTS/Skill 硬约束与审查。

## dispatch-and-return（硬约束）

- 成功 spawn 一个或一批 Agent 后，立即回传任务编号、角色、状态并结束当前 turn；多个 Agent 必须先批量 spawn，再一次性 ACK，禁止边 spawn 边 wait。
- 同一派发 turn 禁止 `wait_agent`、重复 read/status polling、长测试或继续集成；同步等待仅限用户明确要求，且必须先告知会阻塞输入。
- 完成通知、健康巡检、验收和重派只能在后续用户 turn、完成事件 turn 或自动化唤醒中处理；用户新消息优先，依赖队列与路径所有权防冲突。
- Python 只能校验并输出契约，无法控制客户端 turn 结束；不得伪造真实 UI 并发证明。

## 双通道

- fast lane：普通任务直接派一次性 Agent，完成即释放；轻任务用最小派发包，默认 `on-failure` review。
- project lane：复杂、持续、独立领域任务创建或复用长期任务；长期任务只能再派一次性 Agent，禁止更深嵌套。
- 项目 `[agents].max_depth=1`；registry 深度 2 是主控制面代 project task 派发 one-shot 的受管关系，不是 Agent 递归嵌套。
- 高风险任务始终使用全新只读 reviewer；主任务不复用实现上下文做审查。

编排前读 `references/runtime-orchestration.md`，使用 `plan -> enqueue -> dispatch`。队列不限，总运行并发默认 6、写实例 2；依赖、所有权或容量不满足时保持排队。
## 运行规则
- Luna/Terra/Sol 对应 fast/standard/advanced；模型重配置遇到活动/可恢复实例必须输出 `replacement_required`，不得原地改模型。
- 同因失败两次：保存 handoff，停止旧实例，用 `replace` 创建更高档新实例；禁止原地换脑。
- 心跳、超时、依赖、状态、证据、Token 与文件锁写入 `.codex/team/`；`interaction_policy` 默认 dispatch-return；默认 dry-run。
- 外部发布、生产写入、付费动作和凭据变更始终单独取得明确批准。

## 完成闸
声明主控就绪前执行 `team_doctor.py --strict`、orchestrator health、项目测试和高风险 fresh reviewer；`runtime_smoke.py` 只记录真实证据，无法运行时保持 pending/partial。修改 Skill 后运行 deep health、官方 validator（若存在）及 README 链接检查。
