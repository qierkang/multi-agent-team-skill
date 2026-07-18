# Workflow: New Project

1. `inspect_team.py` 必须返回 `new`。
2. `team_init.py --profile auto` dry-run，确认角色、模型、受管路径与 ignored 检查。
3. 用户明确要求落地后才加 `--apply`。
4. 运行 `team_doctor.py` 与 `thread_orchestrator.py health`。
5. 根据真实项目运行测试；创建 explorer 与 fresh reviewer 客户端冒烟，把真实日志传给 `runtime_smoke.py --apply`。

初始化只创建协作层，不创建业务代码。主任务保持 control-plane-only；后续普通工作走 fast lane，复杂持续工作走 project lane。无法执行真实运行态冒烟时 manifest 保持 `pending`；只完成一个角色时保持 `partial_done`，不得创建占位证据或伪造 ready。
