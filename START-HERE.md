# Multi-Agent Team Skill Start Here

## 快速路由

1. 先读 `SKILL.md`。
2. 对目标路径运行 `scripts/inspect_team.py`。
3. `ROUTE=new`：读取 `references/workflow-new-team.md`。
4. `ROUTE=existing-project`：读取 `references/workflow-existing-project.md`。
5. `ROUTE=existing-team` 且 manifest schema=1.0：读取 `references/schema-migration.md`，先 dry-run `team_upgrade.py`。
6. 未知/非受管团队：读取 `workflow-existing-team.md` 与 `migration-rules.md`，只读审计。
7. 需要长期任务时读 `runtime-orchestration.md` 与 `long-thread-policy.md`。
8. 健康、异常或 Token 问题读 `health-anomaly-token.md`。
9. 验收时读 `completion-gate.md`；修改 Skill 后运行 `python3 scripts/health_check.py --deep`。

## 核心承诺

- 新项目按需部署，不机械拉起全部角色。
- 已有项目非侵入升级，不改业务结构和技术栈。
- 受管 v1 可事务升级；未知 schema 先审计且失败关闭。
- 默认只推荐长期任务；显式开启 `controlled-auto` 后主任务才能创建。
- 所有完成结论都必须有可执行回归和运行态证据。
