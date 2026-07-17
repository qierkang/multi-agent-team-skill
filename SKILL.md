---
name: multi-agent-team
description: 当用户要求“初始化多Agent研发团队”“多线程协作”“审计或迁移已有团队”“检查僵尸任务”“团队 doctor”“按我的团队制度初始化”，提到 team-init/team-audit，或显式使用 $multi-agent-team 时触发。用于为新项目或已有项目部署、审计和验证一次性多智能体研发团队；不适用于单文件小修改或纯咨询。
metadata:
  version: "0.2.0"
---

# 多智能体研发团队编排

一个 Skill 统一承载团队检查、初始化、审计、迁移计划、静态验证和双场景回归；`scripts/` 是执行工具，`templates/` 是部署模板的单一事实来源。

| 目标状态 | 路由 | 必须读取 |
|---|---|---|
| 空目录或新项目 | `new` | `references/workflow-new-team.md` |
| 已有业务项目但未部署团队 | `existing-project` | `references/workflow-existing-project.md` |
| 已有 `.codex/agents`、`[agents.*]`、安装清单或常驻任务 | `existing-team` | `references/workflow-existing-team.md` + `references/migration-rules.md` |
| 只检查安装质量 | `doctor` | `references/completion-gate.md` |
| 检查 Skill 自身结构 | `skill-health` | 运行 `python3 scripts/health_check.py` |

用户给出路径后，先运行 `python3 scripts/inspect_team.py --project <项目根目录>`，不得凭目录名判断路由。

## 硬约束

- 初始化器默认 dry-run；旧团队必须先审计，不静默覆盖角色、配置、AGENTS 或业务文件。
- 老项目采用 inspect-first 和非侵入式安装，只追加受管协作块并保留备份。
- `max_depth = 1`、默认 `max_threads = 6`、同时写代码的实例不超过 2 个。
- 运行中不换模型；升级时保存现场并创建更高档位的新实例。
- reviewer 必须是全新只读实例，只接收验收标准、最终 diff 和测试输出。
- 完整产物外置，子任务只回传不超过 10 行摘要和证据路径。

## 完成闸

依次执行 `inspect_team.py`、对应路由脚本、`team_doctor.py` 和 `regression_check.py`。静态检查不能替代目标项目自己的 explorer/reviewer 运行态冒烟；未验证实际模型和沙箱时必须保持 `runtime_smoke_test=pending`。
