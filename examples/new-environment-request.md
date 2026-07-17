# 全新环境调用示例

```text
$multi-agent-team 请检查当前空目录，按项目实际类型初始化一次性多智能体研发团队；先给 dry-run 计划，确认无冲突后执行，并完成 doctor 与运行态冒烟。
```

预期流程：`inspection_done -> plan_ready -> team_installed -> static_validation_done`。

静态安装完成后，目标项目的 `runtime_smoke_test` 仍保持 `pending`，直到实际创建 explorer 与全新 reviewer 完成冒烟。
