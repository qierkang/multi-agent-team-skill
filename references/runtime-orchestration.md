# 运行时长期线程编排

## 控制面边界

主 Codex 任务是唯一长期线程控制面。Python 脚本只生成确定性计划、维护注册表和执行健康检查，不直接调用客户端线程 API。

## 任务输入字段表（`plan --task-json` 的唯一契约）

完整可运行示例见 `examples/task-input.example.json`。字段名以本表为准，不要臆造别名（例如用 `domain` 代替 `domain_key`、`est_days` 代替 `expected_days` 会被拒绝或漏算评分）。

| 字段 | 类型 | 必填 | 作用 |
|---|---|:---:|---|
| `domain_key` | string | 是 | 稳定领域唯一键，推荐 `项目标识::领域标识`；同键只允许一个活跃长期线程 |
| `title` | string | 是 | 人类可读任务名 |
| `owned_paths` | string[] | 否 | 需要独占写入的项目相对路径；用于所有权冲突检测，禁止绝对路径或 `..` |
| `expected_days` | number | 否 | 预计持续天数，`>1` 记 +2 分 |
| `task_packages` | number | 否 | 预计任务包数量，`>=3` 记 +2 分 |
| `independent_boundary` | bool | 否 | 是否有独立业务或目录边界，记 +2 分 |
| `recurring` | bool | 否 | 是否需要持续维护，记 +2 分 |
| `independent_release` | bool | 否 | 是否独立测试或发布，记 +1 分 |
| `decision_retention` | bool | 否 | 是否需要长期保存决策，记 +1 分 |
| `parallelizable` | bool | 否 | 是否可与其他领域并行，记 +1 分 |
| `task_type` | string | 否 | `implementation`/`exploration`/`chore`/`docs`/`research`/`architecture`/`security`/`review`/`migration`，影响模型档位 |
| `risk` | string | 否 | `low`/`medium`/`high`/`critical`，`high`/`critical` 升到 advanced 档 |
| `attempts` | number | 否 | 已失败尝试次数，`>=2` 升到 advanced 档 |

评分阈值：`0-3` 主线程处理，`4-6` 一次性子智能体，`>=7`（`creation_threshold`）创建或复用长期线程。模型档位由 `task_type`/`risk`/`attempts` 决定，映射到项目 `project-state.json` 的 `model_tiers`（安装时可用 `team_init.py --model-fast/--model-standard/--model-advanced` 覆盖为真实模型 ID）。

## 标准流程

1. 将需求整理为任务 JSON（按上表字段），运行 `thread_orchestrator.py plan`。
2. `handle_in_main`：主任务本地执行；`use_subagents`：当前任务内使用一次性角色实例。
3. `recommend_thread`：当前为推荐模式，不创建；`create_thread`：主任务调用客户端，成功后立即 `register --apply`。
4. `reuse_thread`：向 planner 根据注册表和 `domain_key` 返回的 `existing_thread_id` 发送任务包；调用方不得自行指定线程 ID。
5. `queue_or_reuse` / `queue_writer_capacity`：活跃任务或写并发已满，先收口、复用或排队。
6. `blocked_ownership_conflict`：路径所有权冲突，禁止派发。
7. 使用客户端 `wait_threads` 读取里程碑，不按每条 commentary 高频轮询。
8. 收到阶段结果后执行 `update --apply`，并向用户回传不超过 10 行摘要和证据路径。
9. `completed` 必须有证据；归档默认人工确认。

## 创建授权

- `recommend`：只建议创建，不执行客户端创建动作。
- `controlled-auto`：用户在初始化或升级时显式授权主任务按策略自动创建用户可见长期线程。
- 两种模式都不能绕过发布、生产写入、付费动作和凭据修改的独立批准门禁。

## 模型与升级

规划器输出 fast/standard/advanced 及具体模型。运行中的线程不换模型；连续两次同因失败或风险升级时，保存摘要、diff、测试和证据，再创建高档位替代线程。
