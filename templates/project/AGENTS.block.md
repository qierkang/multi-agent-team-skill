<!-- multi-agent-team:start -->
## 多智能体协作制度

- 主任务默认是唯一的 `control-plane-only` 控制面：只做只读判断、拆分、派发、监控、验收、汇报和受管调度状态写入，不修改生产代码。
- 主控任务、主控线程、项目主控和“当前对话设为项目主控”均指普通 Codex 对话控制面，不等价于 Goal。项目主控默认 `controlled-auto`。
- fast lane 将普通任务直接派给一次性 Agent，完成即释放；project lane 为复杂持续任务创建或复用长期领域任务，其 one-shot 由主控制面代为派发，禁止更深嵌套。
- 项目 Codex 配置固定 `agents.max_depth=1`，禁止 Agent 递归创建 Agent；registry 的 depth 2 仅表示主任务 -> project task -> one-shot 的跨任务受管关系。
- 轻任务使用最小派发包并默认仅失败时审查；其余任务使用完整任务包。高风险任务始终由全新 reviewer 审查。
- 子任务回传不超过 10 行摘要，完整报告、日志、diff 和测试输出必须落盘并给出证据路径。
- `.codex/team/thread-registry.json` 是长期任务机读真源；`docs/协作/任务台账.md` 和 `docs/协作/状态快照.json` 是人读证据，聊天记录不是唯一真源。
- 队列数量不限；总运行并发不超过 6，同时写入代码的实例不超过 2；依赖未完成、所有权冲突或容量不足时保持排队。
- reviewer 每次都创建新实例，只接收验收标准、最终 diff、测试输出和必要边界，不继承实现过程。
- Luna/Terra/Sol 按任务风险路由；运行中的实例不换脑。同因失败两次后保存交接现场、关闭旧实例，再用更高档模型创建新实例。
- Token 达到 70% 压缩上下文，85% 冻结扩展范围，100% 保存现场并停止；同因连续失败两次后不得盲目重试。
- Goal policy 固定 `explicit-only`，`control_plane_is_goal=false`；除非用户明确说创建 Goal/使用目标模式/设置目标预算，否则不得调用 Goal、goal-writer 或 `/goal`。
- 若当前线程已有 Goal，报告 `GOAL_MODE=unsupported_for_control_plane_setup`，建议普通新线程；不复用、不新建、不 complete/delete 已有 Goal。
- 初始化/升级措辞即 dry-run 无冲突后 apply 的授权，无冲突时无需二次确认；外部发布、生产写入、付费动作和凭据变更仍需明确批准。
- 这是静态 Skill，无法从代码层绝对阻止客户端违反指令，只能靠 AGENTS/Skill 硬约束和审查。
- 主任务默认消费短摘要，但高风险合并必须检查最终 diff、测试证据和 reviewer 结论。
- 硬约束 dispatch-and-return：成功 spawn 一个或一批 Agent 后立即 ACK 任务编号、角色、状态并结束当前 turn；批量 spawn 后一次性 ACK，禁止边 spawn 边 wait。
- 同一派发 turn 禁止 `wait_agent`、重复 read/status polling、长测试和继续集成；完成通知、健康巡检、验收、重派仅在后续用户 turn、完成事件或自动化唤醒处理。
- 用户新消息优先进入新的调度轮；依赖队列与路径所有权负责避免后台 Agent 并发冲突。Python 不能控制客户端 turn 结束，不得伪造真实 UI 并发证明。
<!-- multi-agent-team:end -->
