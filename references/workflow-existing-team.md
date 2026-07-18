# Workflow: Existing or Unknown Team

已有角色、manifest、运行态、配置角色或 AGENTS 标记时不得直接初始化。

- 受管 schema 1.0 或 schema 2.0 旧 Skill：按 `schema-migration.md` dry-run 升级。
- 当前 2.0.0：doctor + runtime health。
- 未知 schema、非受管、自定义角色或状态冲突：运行 `team_audit.py` 只读审计。

审计报告要列出现有实例、职责、状态、模型、路径、依赖、心跳、风险和建议动作；报告生成不等同迁移执行。旧 reviewer 必须收口，后续高风险审查使用全新实例。任何生产写入、发布和凭据动作都不包含在迁移授权中。
