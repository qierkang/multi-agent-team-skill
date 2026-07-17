# Multi-Agent Team Skill Start Here

## 快速路由

1. 先读 `SKILL.md`。
2. 对目标路径运行 `scripts/inspect_team.py`。
3. `ROUTE=new`：读取 `references/workflow-new-team.md`。
4. `ROUTE=existing-project`：读取 `references/workflow-existing-project.md`。
5. `ROUTE=existing-team`：读取 `references/workflow-existing-team.md` 与 `references/migration-rules.md`。
6. 验收时读取 `references/completion-gate.md`。
7. 修改 Skill 本身后运行 `python3 scripts/health_check.py --deep`。

## 核心承诺

- 新项目按需部署，不机械拉起全部角色。
- 已有项目非侵入升级，不改业务结构和技术栈。
- 已有团队先审计后迁移，不自动清场。
- 所有完成结论都必须有可执行回归和运行态证据。
