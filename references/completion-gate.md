# 完成闸

## 静态闸

0. `python3 scripts/health_check.py` 返回 `STATE=skill_health_passed`。
1. `.codex/config.toml` 可由 `tomllib` 解析。
2. `features.multi_agent = true`。
3. `agents.max_depth = 1`，`agents.max_threads <= 6`。
4. manifest 中所有角色 TOML 存在、可解析、权限符合角色职责。
5. AGENTS 协作标记、台账、任务包、摘要和状态快照均存在。
6. 模板目录不存在本机绝对路径或具体业务残留。
7. doctor 校验 manifest、实际配置和实际角色文件集合一致，角色内容与安装模板一致，受管文件未被 Git 忽略。

## 真实派生闸

在隔离临时 Git 项目执行：

```bash
python3 scripts/team_init.py --project <临时项目> --profile full
python3 scripts/team_init.py --project <临时项目> --profile full --apply
python3 scripts/team_doctor.py --project <临时项目>
```

再次执行检查应路由到 `existing-team`，初始化器应返回 `STATE=needs_audit`，不得覆盖。

运行可执行安全回归：

```bash
python3 scripts/regression_check.py
# STATE=regression_passed; new=passed; existing=passed

PYTHONOPTIMIZE=1 python3 scripts/regression_check.py
# 优化模式同样必须通过，避免测试断言被移除后产生假阳性
```

## 运行态闸

主任务创建一个项目级 explorer 和一个全新 reviewer 做最小真实冒烟，并把 agent id、实际模型、沙箱、退出状态和证据路径写入项目内运行证据。若当前客户端不支持子智能体或无法确认实际沙箱，安装 manifest 保持 `runtime_smoke_test=pending`，必须报告 `STATE=partial_done`，不得称“团队全部就绪”。Skill 源码包自身的前向验证记录放在 `examples/`，不能替代每个目标项目的运行态冒烟。
