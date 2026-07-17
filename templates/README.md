# Templates 单一事实来源

本目录是 `multi-agent-team-skill` 部署到目标项目的模板真源。

| 路径 | 用途 |
|---|---|
| `role-catalog.json` | 角色、模型档位、档案和并发默认值 |
| `agents/*.toml` | 8 个项目级一次性角色模板 |
| `project/AGENTS.block.md` | 追加到目标项目 AGENTS 的受管协作块 |
| `project/config.snippet.toml` | multi-agent 基础配置参考 |
| `project/docs/` | 台账、任务包、摘要和状态快照模板 |
| `reports/团队迁移报告.template.md` | 已有团队只读审计报告骨架 |

修改模板后必须同步运行：

```bash
python3 scripts/health_check.py
python3 scripts/regression_check.py
```
