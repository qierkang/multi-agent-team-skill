# 设计决策

## DEC-0001：一个 Skill，多个内部工具

团队检查、初始化、审计、doctor 与回归统一放在一个 Skill 内，避免用户记忆多个顶层入口。Skill 是编排和安装器，不是常驻团队；真实角色由目标项目 `.codex/agents/*.toml` 定义。

## DEC-0002：6 个核心角色 + 2 个可选角色

不把角色数量固定成组织编制。通用项目部署 6 个核心能力，Web 或 AI/数据项目按需增加 E2E 与证据研究角色；模板数与并发数解耦。

## DEC-0003：Luna / Terra / Sol 三档模型

当前 Codex 已确认支持 `gpt-5.6-luna`、`gpt-5.6-terra`、`gpt-5.6-sol`。快速探索与机械任务使用 Luna，常规实现与验证使用 Terra，架构与独立审查使用 Sol。升级通过一次性新实例完成，不在运行中换模型。

## DEC-0004：状态外置但不禁止主任务复核

子任务完整产物落盘并回传短摘要，以控制主任务上下文；高风险合并仍要求主任务检查 diff、测试证据和独立 reviewer 结论。

## DEC-0005：所有目标先检查再路由

不凭项目名或用户口述判断环境。`inspect_team.py` 只读检查角色文件、配置、安装清单、AGENTS 标记、Git 根和脏状态，再输出 `new / existing-project / existing-team`。

## DEC-0006：只升级已知受管 schema

受管 schema 1.0 可在 dry-run 和备份后事务升级为 2.0；未知 schema、缺失 manifest 或非受管团队仍只生成迁移报告，不覆盖配置、角色或业务文件。

## DEC-0007：模板与展示资产分离

`templates/` 是角色 TOML、项目协作文件和迁移报告的单一事实来源；`assets/` 只保存架构图、流程图、Social Preview 等静态展示资产。脚本不得从 `assets/` 读取部署模板。

## DEC-0008：Skill 健康检查与目标项目 Doctor 分离

`health_check.py` 验证 Skill 源码包自身；`team_doctor.py` 验证某个目标项目的安装结果。两者不能互相替代，深度验收必须再运行新环境和已有环境回归。

## DEC-0009：主任务是唯一长期任务控制面

采用“主任务 -> 按需长期任务 -> 一次性子智能体”。长期任务不得创建长期任务，用户不需要手工跟踪每个下层实例。

## DEC-0010：默认推荐，显式开启受控自动

项目主控默认 `controlled-auto`；`recommend` 仅作为显式兼容模式。无论哪种模式，外部发布、生产写入、付费动作和凭据修改仍需用户批准。

## DEC-0011：注册表是真源，锁与预算是可重建派生状态

`.codex/team/thread-registry.json` 使用 revision、幂等键和进程锁保护写入。所有权锁与预算状态可通过 `reconcile` 从注册表恢复，漂移必须由 health 暴露。

## DEC-0012：Token 资源门禁是运行时合同

70% 要求压缩，85% 冻结扩展范围，100% 保存现场并停止。子任务摘要不超过 10 行，详细产物落盘。

## DEC-0013：主任务默认 control-plane-only

主任务不实现生产代码，只负责只读判断、拆分、派发、监控、验收、汇报和受管调度状态。所有生产实现进入 Agent 实例，避免控制面被执行上下文污染。

## DEC-0014：队列无限但运行容量受控

任务可无限排队，活跃执行统一受总并发 6、写并发 2、依赖和路径所有权约束。容量不足只排队，不丢任务，也不以长期任务数量代替总并发。

## DEC-0015：双通道与有限层级

普通任务进入 fast lane 一次性 Agent；复杂持续工作进入 project lane 长期领域任务。Codex `agents.max_depth=1` 禁止 Agent 递归创建 Agent；registry 的最大 depth 2 是主控制面代 project task 派发一次性 Agent 的跨任务关系，不是 Codex 嵌套配置。

## DEC-0016：失败升级必须换实例

运行中实例不得换模型。同因连续失败两次后保存 handoff，旧实例停止，新实例按 Luna -> Terra -> Sol 升级；Sol 再失败则阻塞。

## DEC-0017：运行态冒烟由真实双角色证据推进

安装和升级只写 `pending`。`runtime_smoke.py` 默认 dry-run，仅接受项目内已存在、非空、非 symlink 的 explorer/reviewer 证据；单侧为 `partial_done`，两侧齐全才为 `runtime_validation_done`，doctor 持续校验状态与证据一致性。

## DEC-0018：health 与 mutation 共用一致性锁

health 必须在 mutation 使用的同一 runtime lock 下读取 registry、ownership locks、budget 和人读快照。这样仍能检测静态 drift，但不会把正常多文件写入的中间窗口误报为 drift。

## DEC-0019：Goal 不属于控制面

主控任务、主控线程、项目主控和当前对话设为项目主控均表示普通 Codex 对话控制面。`goal_policy=explicit-only` 且 `control_plane_is_goal=false`；project task/长期领域任务与 Codex Goal 明确分离。已有 Goal 的线程报告 `unsupported_for_control_plane_setup`，不复用或新建。
