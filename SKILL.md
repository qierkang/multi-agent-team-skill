---
name: multi-agent-team
description: 当用户要求初始化或升级多 Agent 研发团队、动态创建长期任务、多任务并行、团队健康检测、僵尸任务、Token 节省、异常恢复，提到 team-init/team-upgrade/team-audit，或显式使用 $multi-agent-team 时触发。不适用于单文件小修改或纯咨询。
metadata:
  version: "1.0.1"
---

# 受控多智能体团队

主任务是唯一控制面；按评分在“主任务直接做 / 一次性子智能体 / 长期任务”中选择。长期任务可派生一次性子智能体，但不得再创建长期任务。

| 目标状态 | 路由 | 必须读取/执行 |
|---|---|---|
| 空目录或新项目 | `new` | `references/workflow-new-team.md` + `scripts/team_init.py` |
| 旧项目未部署团队 | `existing-project` | `references/workflow-existing-project.md` + `team_init.py` |
| 受管 v1 团队 | `existing-team:v1` | `references/schema-migration.md` + `team_upgrade.py` |
| 未知/非受管团队 | `existing-team:audit` | `workflow-existing-team.md` + `team_audit.py` |
| 规划长期任务 | `orchestrate` | `runtime-orchestration.md` + `thread_orchestrator.py plan` |
| 健康/异常/Token | `runtime-health` | `health-anomaly-token.md` + `thread_orchestrator.py health` |

用户给出路径后必须先运行：

```bash
python3 scripts/inspect_team.py --project <项目根目录>
```

## 默认策略

- `recommend`：默认模式，评分达标只推荐新长期任务。
- `controlled-auto`：用户显式开启后，主任务可调用客户端任务工具创建，再用 `register --apply` 记录返回 ID。
- 运行时脚本本身不伪造任务 ID，不绕过客户端授权，不自动执行外部发布、生产写入或凭据变更。
- 默认使用当前 Codex 的 Luna/Terra/Sol 三档模型；订阅不支持或需自定义时，用 `--model-fast/--model-standard/--model-advanced` 安全覆盖，并以运行态冒烟确认可用性。
- 构造 `thread_orchestrator.py plan` 的任务 JSON 前，先读 `references/runtime-orchestration.md` 的“任务输入字段表”和 `examples/task-input.example.json`，字段名以该表为准（如 `domain_key`/`expected_days`，勿用别名）。

## 生产级约束

- 初始化/升级默认 dry-run；未知 schema 失败关闭；不覆盖业务文件、自定义配置或角色。
- 每个派发包含目标、所有权、验证、停止条件；同时写入最多 2，路径互斥。
- 同 `domain_key` 只有一个活跃长期任务；写入使用锁、revision 与幂等键。
- reviewer 始终为全新只读实例；完成状态必须有证据路径。
- Token 70% 压缩、85% 冻结范围、100% 停止；同因两次失败后升级而非盲目重试。
- 子任务回传不超过 10 行；完整 diff、日志和测试落盘，主任务回传阶段进度。

## 完成闸

执行 `team_doctor.py` + `thread_orchestrator.py health` + 项目自身测试 + 全新 explorer/reviewer 运行态冒烟。修改 Skill 本身后必须运行 `python3 scripts/health_check.py --deep`。
