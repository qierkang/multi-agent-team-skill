# Templates 单一事实来源

`templates/` 是部署到目标项目的业务中性模板真源；`assets/` 仅保存静态展示资产，两者不得混用。

| 路径 | 用途 |
|---|---|
| `role-catalog.json` | 8 个角色、Luna/Terra/Sol 档位和并发默认值 |
| `agents/*.toml` | 项目级一次性角色模板 |
| `project/AGENTS.block.md` | control-plane-only、双通道与审查制度 |
| `project/docs/最小派发包.template.md` | 低风险 fast lane 轻任务 |
| `project/docs/任务包.template.md` | 常规与 project lane 完整任务包 |
| `project/docs/` | 台账、摘要、快照和异常记录 |
| `project/team/` | schema 2.0 运行态模板 |
| `reports/团队迁移报告.template.md` | 未知团队只读审计报告 |

模板禁止客户名、业务项目名、本机绝对路径、Token、Cookie、密码或环境专属凭据。修改后运行 `python3 scripts/health_check.py --deep`。
