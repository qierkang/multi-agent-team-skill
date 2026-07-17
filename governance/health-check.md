# Skill 健康检查

## 快速检查

```bash
python3 scripts/health_check.py
```

必须输出 `STATE=skill_health_passed`，检查内容包括：

- 根入口不超过 80 行并保持稳定 Skill 名称。
- `references/`、`scripts/`、`templates/`、`examples/`、`governance/` 分层存在。
- 角色目录、角色目录清单和 Profile 引用一致。
- TOML、JSON 和 Python 脚本可解析。
- 不存在旧模板路径和本机用户绝对路径。

## 深度检查

```bash
python3 scripts/health_check.py --deep
```

除快速检查外，还必须通过：

- 全新环境初始化回归。
- 已有业务项目非侵入式回归。
- 受管 v1 非空任务升级、未知团队只读审计和安全门禁回归。
- 并发注册、所有权、Token、snapshot/registry 等价性和 reconcile 故障回归。

深度检查最终应输出：

```text
STATE=regression_passed; new=passed; existing=passed; runtime=passed
STATE=skill_health_passed
```
