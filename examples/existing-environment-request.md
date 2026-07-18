# 已有环境调用示例

## 已有业务项目

```text
multi-agent-team-skill 帮我初始化这个已有项目，不要改业务代码；先 dry-run。
```

inspect 自动路由 `existing-project`，安装器只追加受管协作层并备份已有配置/AGENTS。

## 受管旧团队

```text
multi-agent-team-skill 帮我升级这个项目。
```

inspect 自动区分 `existing-team:v1`、`existing-team:v2-upgrade` 与当前 v2；升级默认 dry-run。

## 未知或自定义团队

```text
multi-agent-team-skill 帮我检查这个团队，不要覆盖现有角色。
```

未知 schema 或自定义受管资产只读审计，`audit_report_ready` 不代表迁移已执行。
