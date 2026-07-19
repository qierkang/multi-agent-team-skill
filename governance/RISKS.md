# 风险清单

## Open Risks

### R-001：Codex 配置字段未来变化

- 风险：`agents` 或角色 TOML 字段可能随 Codex 升级变化。
- 应对：维护时核对当前 CLI 版本和官方 config schema，并用目标版本解析/冒烟。

### R-002：自动档案识别不完整

- 风险：多语言或特殊项目可能被 `auto` 归入较小档案。
- 应对：dry-run 明示检测依据，允许用户显式指定 `web / ai-data / full`。

### R-003：静态 doctor 不等于真实子智能体可运行

- 风险：配置解析通过，但客户端未加载角色或实际沙箱不符合预期。
- 应对：完成闸要求额外创建 explorer 与全新 reviewer 做运行态冒烟；缺失时只能报告 partial_done。

### R-004：既有项目配置冲突

- 风险：项目已有 `[features]` 或 `[agents]` 不同值。
- 应对：默认阻断，不静默覆盖；已有团队交由 `$multi-agent-team` 审计模式生成迁移计划。

### R-005：运行时任务状态无法从文件完整推断

- 风险：仅检查 TOML 不能知道任务是否失联、等待输入或已完成。
- 应对：审计器要求客户端提供符合快照结构的任务数据；没有快照时明确标记未核验，不猜测、不自动归档。

### R-006：客户端长期任务 API 与脚本不在同一事务中

- 风险：客户端已创建任务，但本地注册失败，或反向状态漂移。
- 应对：客户端返回 ID 后再登记；使用幂等键、revision、恢复日志与 health/reconcile；不伪造任务 ID。

### R-007：默认模型与目标订阅可用范围不一致

- 风险：`gpt-5.6-luna/terra/sol` 是当前 Codex 默认三档模型，但不同订阅或未来版本的可用范围可能不同。
- 应对：
  - `team_init.py` 和 `team_upgrade.py` 支持 `--model-fast/--model-standard/--model-advanced`；只有无活动实例或仅终态记录时才同步角色 TOML、项目策略和安全可迁移记录。
  - 模型 ID 经过白名单校验和 TOML 安全序列化；v2 重配置先 dry-run、备份并事务写入，活动/可恢复实例输出 `replacement_required` 且零写入，旧档位有歧义时拒绝猜测。
  - 模型映射集中在项目策略与角色目录；安装后必须做真实 explorer/reviewer 冒烟，不以静态校验代替。
  - 回归固定校验默认安装、自定义注入、恶意输入拒绝和 v2 重配置链路。

### R-008：AGENTS 语义冲突检测无法理解所有自然语言改写

- 风险：确定性规则能阻断已知“快速直改/聚焦开发/主任务自行实现”表述，但无法证明覆盖所有同义改写或祖先目录动态注入规则。
- 应对：命中即失败关闭；未命中仍需 runtime smoke 和 fresh reviewer。后续用真实事故样本扩充规则，不把关键词检查宣称为绝对运行时隔离。

## Closed Risks

| ID | 描述 | 修复 |
|---|---|---|
| C-001 | 受管目录符号链接可能导致越界写入 | 安装前逐级拒绝符号链接并校验 resolve 边界 |
| C-002 | 多文件写入中途失败可能形成半安装 | 事务式写入，异常时恢复原文件并删除本轮新文件 |
| C-003 | 非预期 I/O 异常可能无机读 STATE | 安装、doctor、audit 统一兜底并输出失败状态 |
| C-004 | 空目录、已有项目和已有团队可能走错流程 | 新增只读 inspect-first 路由和三态识别回归 |
| C-005 | 旧项目业务文件可能被安装器误改 | 已有环境回归固定校验业务文件哈希、原配置内容和备份 |
| C-006 | 模板混放在 assets 导致职责不清和引用漂移 | 模板统一迁入 `templates/`，新增健康检查阻止旧路径回归 |
| C-007 | 只验证目标项目、不验证 Skill 包自身 | 新增快速/深度 `health_check.py` 与统一 install doctor |
| C-008 | 状态快照使用 `tasks`、审计器期待 `threads` | v2 schema 统一为 `threads`，升级器保留 v1 数据 |
| C-009 | 所有权锁或预算派生状态漂移 | health 在 runtime lock 下强制比对 registry revision，`reconcile` 可恢复且并发写中间态不误报 |
| C-010 | v1 `evidence` 被审计器误判为缺证据 | 审计同时归一 `evidence` 与 `evidence_paths`，确定性回归覆盖两种字段 |
| C-011 | runtime smoke 永久 pending 或被占位证据伪造完成 | 受控命令、角色分栏、非空真实文件门禁、状态迁移和 doctor 回归闭环 |
| C-012 | 模型重配置原地改写活动实例 | upgrade 持 runtime lock；活动/可恢复实例零写入并输出 replacement_required，升级只经新实例 handoff/replace |
| C-013 | 假、越界或 symlink evidence 通过完成闸 | audit、update、migration、doctor、health、runtime smoke 共用项目内真实非空普通文件校验 |
| C-014 | v2 `--thread-mode controlled-auto` 被静默忽略 | 显式模式更新同步 manifest/project-state，doctor 一致性校验和 project dispatch 回归覆盖 |
| C-015 | queued -> blocked -> active 绕过派发门禁 | blocked 恢复强制 instance/start/handoff、依赖、父任务、模式、domain、所有权与容量复验 |
| C-016 | AGENTS 同时允许主任务直改且含 control-plane marker，doctor 仍假通过 | 共享非受管区冲突检测接入 init/upgrade/audit/doctor 并增加真实复现回归 |
| C-017 | 项目标题看似主控，但 manifest 无线程绑定或 runtime smoke 仍 pending | 新增显式绑定命令与 strict doctor 完成闸 |
| C-018 | worktree 主控直接写入另一 checkout | AGENTS 与完整/最小任务包固定 inspect 根目录相对路径和跨工作区停止条件 |

## v2 开放风险

- 客户端真实 Agent 创建、模型订阅和沙箱权限无法由确定性脚本完全证明；每个目标项目仍需运行态冒烟。
- 冒烟命令可验证证据文件存在、非空和角色覆盖，但无法从本地文件内容独立证明远端客户端真实性；操作者仍必须保存真实输出，无法运行时保持 pending/partial。
- 无限队列不会丢任务，但长期积压需外部监控和人工优先级治理；health 当前报告数量，不自动删除。
- 超时检测依赖本机 UTC 时间与心跳写入；时钟漂移或客户端未上报时会降级/失败关闭。
- Sol 同因失败两次后无更高自动档位，只能阻塞并请求决策。
