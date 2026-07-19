# 变更记录

## 2.0.4 - 2026-07-19

- 修复 AGENTS 受管块外仍允许“快速直改/聚焦开发/主任务自行实现”时 doctor 假通过；init、upgrade、audit、doctor 统一失败关闭检测。
- 新增 `bind_control_task.py` 与 `team_doctor.py --strict`：指定主控只有真实 thread/host/title/pin 绑定和 explorer/reviewer smoke 齐全才算完成。
- 完整/最小派发包和控制面契约禁止写入 inspect 根目录之外的另一 checkout/worktree。
- 新增 control-plane policy 回归，覆盖冲突安装阻断、升级拒绝、audit 报告、strict 门禁、dry-run 绑定和伪 pin 拒绝。

## 2.0.3 - 2026-07-18

- 修复 Goal 抢占：普通 Codex 对话控制面不创建或复用 Goal；初始化/升级无冲突时 dry-run 后直接 apply。
- 新增 `goal_policy=explicit-only` 与 `control_plane_is_goal=false`，项目主控默认 `controlled-auto`，并由 doctor/health 校验。
- 增加触发短语、Goal 禁止路由、已有 Goal unsupported 和无需二次确认回归；诚实披露静态 Skill 无法绝对阻止客户端违规。

- 修复主控 spawn Agent 后在同一 turn wait、轮询、长验收造成后续用户消息排队的问题。
- 固化 `dispatch-and-return`：批量 spawn 后一次性 ACK 任务编号、角色、状态并立即 return；禁止同 turn `wait_agent`、polling、长测试和继续集成。
- 将完成通知、health、验收、重派延后至用户 turn、完成事件 turn 或自动唤醒；以依赖队列和路径所有权保护新调度轮。
- 新增 project-state/template `interaction_policy`，doctor、health_check 与确定性回归验证 same-turn wait 禁止和输出契约。
- 明确 Python 无法控制客户端 turn 结束，验证不伪造真实 UI 并发证明；同步更新中英繁 README、references、governance 与验证证据。

## 2.0.2 - 2026-07-18

- 修复主控 spawn Agent 后在同一 turn wait、轮询、长验收造成后续用户消息排队的问题。
- 固化 `dispatch-and-return` 与后续 turn/event 处理边界。

## 2.0.1 - 2026-07-18

- inspect-first 根据 README H1、项目 manifest、目录名确定主控显示名。
- inspect、初始化、升级和健康路由输出 `codex_app__set_thread_title` 建议动作；Python 不伪造客户端成功，客户端不可用时保持 `TITLE_RENAME=pending`。
- 已是最新版的健康检查路径同样执行标题建议。

## 2.0.0 - 2026-07-18

- 主任务默认 `control-plane-only`，planner 不再允许主任务直接修改生产代码。
- 增加 fast lane / project lane、无限队列、依赖、层级、总并发 6 与写并发 2。
- 轻任务使用最小派发包和 on-failure review；high/critical 始终 fresh reviewer。
- 增加心跳、超时、同因失败指纹、handoff 与 Luna/Terra/Sol 新实例升级。
- inspect 自动细分当前团队与待升级 v2 团队；用户无需提供内部编排术语。
- schema 1.0 与 Skill 1.x 均可事务、可备份、确定性升级到 Skill 2.0.0。
- 新增 inspect、队列、依赖、嵌套、替换实例、README 链接和 `PYTHONOPTIMIZE=1` 回归。
- 审计器兼容旧 `evidence` 与新 `evidence_paths`；health 与 mutation 共用 runtime lock，避免并发写中间态误报 drift。
- 新增 `runtime_smoke.py`，以真实 explorer/reviewer 证据推进 pending -> partial_done -> runtime_validation_done，并由 doctor 失败关闭校验。
- 明确 Codex `agents.max_depth=1` 与 registry 受管 depth 2 的语义边界，禁止把跨任务控制层误配为 Agent 递归深度。
- 模型重配置不再改写活动/可恢复实例；升级器输出 `replacement_required`，模型升级只能通过 handoff 新实例接替。
- evidence 统一要求项目相对、无 `..`、存在、非空且非 symlink，并由 update、migration、doctor、health 与 runtime smoke 共用校验。
- 已有 v2 团队可显式事务更新 `--thread-mode controlled-auto`；blocked 恢复重新校验 dispatch、handoff、依赖、所有权和并发门禁。
- 中英繁文档、references、templates、governance 与验证证据同步升级。

## 1.0.1 - 2026-07-17

- `team_init.py` 新增 `--model-fast/--model-standard/--model-advanced`，可按订阅覆盖当前 Codex 默认三档模型，并同步角色 TOML 与 `project-state.json`。
- `team_doctor.py` 按项目实际 `model_tiers` 校验角色模型，兼容真实模型注入且仍逐字节校验除 model 行外的模板一致性（防篡改）。
- `inspect_team.py` 输出 `ROUTE_DETAIL` 与 `SCHEMA_VERSION`，将已有团队细分为 `existing-team:v1 / v2 / audit`，与 SKILL.md 路由表对齐。
- 新增 `examples/task-input.example.json` 与 `references/runtime-orchestration.md` 的“任务输入字段表”，固定 `plan` 的任务 JSON 字段契约。
- 新增繁体中文文档 `docs/README_zh-tw.md`，并接入中英文语言导航。
- 回归新增：模型注入三方一致性、v1 路由细分两条断言。
- 模型 ID 采用白名单校验和安全 TOML 序列化；v2 团队支持事务重配置模型并安全映射已登记任务。
- 任务 JSON 改为严格字段与类型契约；线程复用只以注册表中的 `domain_key` 为准，不再接受无效的调用方线程 ID。
- README 注册示例改用 planner 返回模型，并把繁体文档与任务示例纳入健康门禁。
- GitHub Actions 升级到 Node 24 运行时的 checkout/setup-python v6，并收紧为只读仓库权限。
- v1 迁移兼容旧快照的 `evidence` 字段，保留完成证据并避免已完成任务被误降级。

## 1.0.0 - 2026-07-17

- 升级为“主任务 -> 按需长期任务 -> 一次性子智能体”受控编排。
- 新增 `recommend` / `controlled-auto` 模式、确定性评分、模型分档和任务复用。
- 新增 v2 注册表、所有权锁、Token 预算、恢复日志、revision、幂等键和 reconcile。
- 新增受管 v1 -> v2 事务升级，未知 schema 失败关闭。
- 新增心跳、领域重复、所有权冲突、证据闸和 Token 70/85/100 健康检查。
- 新增运行时故障回归，与新环境、旧项目回归共同组成深度验收。

## 0.2.0 - 2026-07-17

- 对齐 Harness Engineering Skill 设计规范。
- 模板独立到 `templates/`，展示资产保留在 `assets/`。
- 增加 Skill 自身健康检查与统一安装、同步、doctor 入口。
- 保持新环境、已有项目和已有团队的原有安全路由与行为不变。

## 0.1.0 - 2026-07-17

- 将原 `team-init` 与 `team-audit` 合并为统一 `multi-agent-team-skill`。
- 新增统一检查路由、已有项目非侵入流程和双场景回归。
- 收口角色、配置、台账、迁移报告、doctor 和治理资产的唯一真源。
