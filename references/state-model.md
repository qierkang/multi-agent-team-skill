# 机读状态模型

| 状态 | 含义 | 下一步 |
|---|---|---|
| `inspection_done` | 路由识别完成，未写入 | 按 `ROUTE` 进入对应工作流 |
| `inspection_failed` | 路径、TOML 或 Git 检查失败 | 修复输入或项目状态后重试 |
| `plan_ready` | 初始化 dry-run 可执行 | 审阅后显式添加 `--apply` |
| `plan_blocked` | 有冲突或被忽略路径 | 先人工处理，不绕过门禁 |
| `needs_audit` | 检测到已有团队 | 运行 `team_audit.py` |
| `team_installed` | 文件事务写入完成 | 运行 doctor 与运行态冒烟 |
| `install_failed` | 安装失败并已尽力回滚 | 检查错误和备份，不重复盲试 |
| `audit_report_ready` | 只读审计报告已生成 | 用户确认迁移计划后另行执行 |
| `audit_failed` | 审计输入或报告路径不合法 | 修正快照或输出路径 |
| `static_validation_done` | 静态结构、模型和沙箱声明通过 | 做目标项目运行态冒烟 |
| `static_validation_failed` | 静态安装不完整或不安全 | 修复后重新验证 |
| `runtime_validation_done` | 编排器已创建目标项目 explorer 和全新 reviewer，实际模型、权限、工具及退出状态均有证据 | 可声明目标团队运行态就绪 |
| `partial_done` | 静态安装完成，但当前客户端无法执行或证明运行态冒烟 | 保持 manifest 的 `runtime_smoke_test=pending`，不得声称完全就绪 |
| `new_environment_regression_passed` | 全新环境回归通过 | 可继续已有环境回归 |
| `existing_environment_regression_passed` | 已有项目/团队回归通过 | 可进入总验收 |
| `regression_passed` | 两类环境总回归通过 | 结合独立审查给出交付结论 |
