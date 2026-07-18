# 变更记录

## 2.0.0 - 2026-07-18

- 确立 control-plane-only 与 fast/project 双通道。
- 队列与并发解耦，增加依赖、handoff、超时、失败替换和分级 review。
- 将优化模式回归、README 链接与生产评分纳入完成闸。
- 补齐 legacy evidence 审计、health 锁一致快照和 runtime smoke 状态/证据闭环回归。
- 固化 `agents.max_depth=1`，将 registry depth 2 定义为主控制面管理的跨任务关系。
- 修复活动实例被模型重配置原地改写；改为 runtime lock 下零写入 `replacement_required`。
- 统一 update/migration/doctor/health/runtime smoke 的真实 evidence 路径校验，并补绝对、越界、缺失、空文件与 symlink 回归。
- 使已有 v2 团队的显式 `--thread-mode controlled-auto` 事务生效，并收紧 blocked 恢复的完整 active admission 门禁。

## 1.0.1 - 2026-07-17

- 增加安全模型覆盖和 v2 事务重配置，模型 ID 注入拒绝引号、换行及控制字符。
- 将任务输入升级为严格字段与类型合同，线程复用只信任注册表领域键。
- 补齐 v1/v2 模型迁移、繁体文档、任务输入示例和新增资产健康门禁。

## 1.0.0 - 2026-07-17

- 引入 schema 2.0 控制面和五类项目运行时状态。
- 明确长期任务的创建阈值、单领域唯一活跃任务、模型升级、所有权和外部动作边界。
- 修复状态快照 `tasks` / `threads` 合同分歧。
- 增加 CAS revision、幂等注册、本地进程锁、派生状态漂移检测与恢复。
- 将旧团队政策从“全部只审计”细化为“已知受管 schema 可升级，未知 schema 失败关闭”。

## 0.2.0 - 2026-07-17

- 按 Harness Engineering 结构将部署模板从 `assets/` 迁入独立 `templates/` 单一事实来源。
- `assets/` 收口为静态展示资产目录，避免模板与图片职责混杂。
- 新增 Skill 自身健康检查，覆盖入口长度、目录分层、角色/Profile 一致性、模板解析、脚本编译和路径去本机化。
- 新增 `install/setup.sh`、默认 dry-run 的 `install/sync.sh` 和深度 `install/doctor.sh`。
- 新增治理索引与健康检查清单，明确 Skill 健康检查和目标项目 doctor 的边界。

## 0.1.0 - 2026-07-17

- 将原团队初始化与团队审计能力合并为 `multi-agent-team-skill` 单一入口。
- 新增 inspect-first 路由，区分全新环境、已有业务项目和已有团队。
- 新增 core、web、ai-data、full 四种角色档案。
- 新增 6 个核心角色和 2 个可选角色模板。
- 新增默认 dry-run 的安全安装器、只读审计器、静态 doctor、协作台账与任务包模板。
- 新增完成闸和隔离派生回归快照。
- 增加受管路径符号链接阻断、多文件失败回滚和统一机读错误状态。
- 增加全新环境与已有环境两套独立可执行回归。
- 修复目录型 `.gitignore` 规则漏检，改为逐个核验所有实际受管文件及备份探针。
- 增加父 Git 工作树识别、深层备份符号链接阻断、doctor 符号链接门禁和可执行安全回归脚本。
