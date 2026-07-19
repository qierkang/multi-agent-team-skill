# Workflow: Existing or Unknown Team

已有角色、manifest、运行态、配置角色或 AGENTS 标记时不得直接初始化。

- 受管 schema 1.0 或 schema 2.0 旧 Skill：按 `schema-migration.md` dry-run 升级。
- 当前 2.0.4：doctor + runtime health；确认 `interaction_policy` 后再进入后续 turn 验收。
- inspect、升级或最新版 health 成功后，主控读取 `TITLE_SUGGESTED` 并调用 `codex_app__set_thread_title`；客户端不可用只记 `TITLE_RENAME=pending`。
- 未知 schema、非受管、自定义角色或状态冲突：运行 `team_audit.py` 只读审计。

审计报告要列出现有实例、职责、状态、模型、路径、依赖、心跳、风险和建议动作；报告生成不等同迁移执行。旧 reviewer 必须收口，后续高风险审查使用全新实例。任何生产写入、发布和凭据动作都不包含在迁移授权中。


## Goal boundary
- `goal_policy=explicit-only`; `control_plane_is_goal=false`; project control defaults to `controlled-auto`.
- A project task/long-lived domain task is not a Codex Goal. An active Goal reports `GOAL_MODE=unsupported_for_control_plane_setup` and is never reused or created by this Skill.
