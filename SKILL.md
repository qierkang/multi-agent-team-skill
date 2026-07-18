---
name: multi-agent-team
description: 用户要求用 multi-agent-team-skill 初始化、升级、检查项目，或需要受控多 Agent 并行、长期领域任务、队列、心跳、Token 与失败恢复时触发。普通单文件修改和纯咨询不触发。
metadata:
  version: "2.0.0"
---

# Multi-Agent Team v2

主任务默认是唯一 `control-plane-only` 控制面：只做只读判断、拆分、派发、监控、验收、汇报和受管调度状态写入，不写生产代码。

用户给出项目路径后，无需询问 orchestrator 等内部术语，必须先执行：

```bash
python3 scripts/inspect_team.py --project <项目根目录>
```

| inspect 结果 | 动作 |
|---|---|
| `new` / `existing-project` | 读对应 workflow，dry-run `team_init.py` |
| `existing-team:v1` / `v2-upgrade` | 读 `schema-migration.md`，dry-run `team_upgrade.py` |
| `existing-team:audit` | 运行只读 `team_audit.py`，未知 schema 失败关闭 |
| `existing-team:v2` | 运行 `team_doctor.py` 与 orchestrator `health` |

用户明确要求“升级并开启受控自动”时，Skill 可为受管 v2 团队选择 `team_upgrade.py --thread-mode controlled-auto`；这不替代任何外部动作审批。

## 双通道

- fast lane：普通任务直接派一次性 Agent，完成即释放；轻任务用最小派发包，默认 `on-failure` review。
- project lane：复杂、持续、独立领域任务创建或复用长期任务；长期任务只能再派一次性 Agent，禁止更深嵌套。
- 项目 `[agents].max_depth=1`；registry 深度 2 是主控制面代 project task 派发 one-shot 的受管关系，不是 Agent 递归嵌套。
- 高风险任务始终使用全新只读 reviewer；主任务不复用实现上下文做审查。

编排前读 `references/runtime-orchestration.md`，使用 `plan -> enqueue -> dispatch`。队列不限，总运行并发默认 6、写实例 2；依赖、所有权或容量不满足时保持排队。

## 运行规则

- Luna/Terra/Sol 对应 fast/standard/advanced；模型重配置遇到活动/可恢复实例必须输出 `replacement_required`，不得原地改模型。
- 同因失败两次：保存 handoff，停止旧实例，用 `replace` 创建更高档新实例；禁止原地换脑。
- 心跳、超时、依赖、状态、证据、Token 与文件锁写入 `.codex/team/`；默认 dry-run。
- 外部发布、生产写入、付费动作和凭据变更始终单独取得明确批准。

## 完成闸

执行 `team_doctor.py`、`thread_orchestrator.py health`、项目测试和高风险 fresh reviewer；用 `runtime_smoke.py` 记录真实客户端证据，无法运行时保持 pending/partial。修改 Skill 后运行 `python3 scripts/health_check.py --deep`、官方 validator（若存在）及 `python3 scripts/check_readme_links.py`。
