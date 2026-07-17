# 贡献指南

1. 先读 `AGENTS.md`、`SKILL.md` 和适用 workflow。
2. 角色变更以 `templates/agents/*.toml` 和 `templates/role-catalog.json` 为真源；`assets/` 只存放静态展示资产。
3. 工具行为变化必须同步 README、references 与 governance。
4. 禁止把本机绝对路径、业务项目名、凭据和临时日志写入模板。
5. 提交前运行：

```bash
python3 scripts/health_check.py --deep
PYTHONOPTIMIZE=1 python3 scripts/regression_check.py
bash scripts/verify_assets.sh .
```

只有新环境和已有环境都通过，且公开图片、README 链接均通过校验，才能更新发布状态。请同时确认 `.github/` 社区文件未被误删，提交内容不含本机绝对路径、凭据、客户信息或临时产物。
