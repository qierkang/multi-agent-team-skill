# 确定性迁移

## 支持路径

- schema 1.0 受管团队 -> schema 2.0 / Skill 2.0.0。
- schema 2.0 且 Skill 1.x -> Skill 2.0.0 patch migration。
- 当前 2.0.0 -> `already_current`。
- 未知 schema、非受管 manifest 或自定义受管角色 -> 只读审计，失败关闭。

## 2.0.0 新增字段

迁移为每条既有记录确定补齐 `instance_id`、`lane`、`depth`、`parent_thread_id`、`dependencies`、`model_tier`、`started_at`、`timeout_seconds`、`failure_history`、`handoff_path`、`generation`、`replaces_instance_id`、派发包与 review 策略。旧 `evidence` 与 `evidence_paths` 都迁入 `evidence_paths`，且每个路径必须是项目内已存在、非空、非 symlink 的真实文件，否则迁移失败关闭。

项目策略确定升级为 `control-plane-only`、fast/project 双通道、总并发 6、写并发 2、无限队列和失败替换策略。业务源码、无关配置、线程 ID、状态、证据和模型档位不猜测改写。

受管 v2 可显式用 `--thread-mode controlled-auto` 更新 manifest 与 project-state；未提供参数时保留当前模式。模型档位变更若发现活动或可恢复实例，升级器输出 `STATE=replacement_required` 且不写任何文件；运行中换模只能走 fail/handoff/replace 新实例流程。

## 流程

1. inspect-first，确认 route 与 dirty 状态。
2. dry-run `team_upgrade.py`，检查备份、受管目标和冲突。
3. `--apply` 前再次确认没有自定义受管角色漂移或 symlink/ignored 风险。
4. 事务写入并保留 `.codex/backups/multi-agent-team/<timestamp>/`。
5. 运行 doctor、runtime health、项目测试和必要的 fresh reviewer。
