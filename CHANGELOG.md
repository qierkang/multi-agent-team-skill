# 变更记录

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
