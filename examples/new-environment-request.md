# 全新环境调用示例

```text
multi-agent-team-skill 帮我初始化这个项目。先检查，默认只给 dry-run 计划。
```

Skill 自动执行 inspect-first，不要求用户选择 orchestrator 或 lane。预期静态流程：`inspection_done -> plan_ready -> team_installed -> static_validation_done`。

安装后主任务为 control-plane-only；普通工作派 fast lane 一次性 Agent，复杂持续工作进入 project lane。真实 Agent 模型、沙箱和工具可用性仍需目标项目运行态冒烟，未执行时只能报告 partial。
