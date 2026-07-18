# Multi-Agent Team Skill v2 Start Here

## 用户入口

用户只需说“用 multi-agent-team-skill 初始化 / 升级 / 检查这个项目”并提供路径。不要要求用户选择 orchestrator、lane 或 schema。

1. 读 `SKILL.md`。
2. 只读运行 `python3 scripts/inspect_team.py --project <path>`。
3. 按 `ROUTE_DETAIL` 读取 `references/INDEX.md` 中对应 workflow。
4. 初始化或升级先 dry-run；只有用户明确要求落地时加 `--apply`。
5. 未知团队先审计，禁止覆盖现有角色、配置、状态或业务文件。

## 执行入口

| 需求 | 命令 |
|---|---|
| 初始化 | `team_init.py` |
| 受管升级 | `team_upgrade.py` |
| 未知团队审计 | `team_audit.py` |
| 静态检查 | `team_doctor.py` |
| 任务规划与队列 | `thread_orchestrator.py plan/enqueue/dispatch` |
| 心跳、失败、替换 | `thread_orchestrator.py update/fail/replace/health` |
| 客户端冒烟证据 | `runtime_smoke.py`（pending -> partial_done -> runtime_validation_done） |
| Skill 完整验证 | `health_check.py --deep` |

## 不变量

- 主任务 `control-plane-only`，不写生产代码。
- fast lane 一次性 Agent；project lane 的 one-shot 由主控制面代为派发；Codex `agents.max_depth=1`，registry 受管关系最多 depth 2。
- 队列不限、总并发 6、写并发 2、所有权互斥。
- 轻任务最小包 + on-failure review；高风险 fresh reviewer。
- 运行中不换脑；同因两次失败后以 handoff 创建更高档新实例。
- 默认 dry-run；外部高风险动作独立审批。
