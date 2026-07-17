# Schema 版本与老项目迁移

## 支持范围

- Schema 2.0：当前生产格式。
- Schema 1.0：仅允许通过 `team_upgrade.py` 迁移。
- 未知版本：阻断并要求人工审计，不能猜测转换。

## 迁移步骤

1. `inspect_team.py` 与 `team_audit.py` 只读收集配置、Git、角色和运行时快照。
2. `team_upgrade.py` 默认 dry-run，列出新增状态文件、AGENTS 受管块更新和备份计划。
3. `--apply` 前备份 manifest、AGENTS 和将被修改的受管文件。
4. 事务写入 Schema 2.0 状态；保留业务文件、角色 TOML、现有配置和运行证据。
5. 执行 doctor、runtime health、新 explorer/reviewer 冒烟和目标项目业务验证。
6. 失败时恢复备份并删除本轮新文件；迁移过程记录到 recovery journal。
