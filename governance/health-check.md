# v2 健康检查

修改 Skill 后运行：

```bash
python3 scripts/health_check.py --deep
PYTHONOPTIMIZE=1 python3 scripts/regression_check.py
python3 scripts/check_readme_links.py
bash scripts/verify_assets.sh
```

检查项：

- SKILL 2.0.3、约 40 行入口和 inspect-first 路由；
- dispatch-and-return、`interaction_policy` 与 same-turn wait/poll/长验收禁止；Python 不伪造客户端 UI 并发证据；
- 标题回归覆盖新目录、已有项目、已有团队、README H1 与 manifest/目录 fallback；客户端动作保持 pending 诚实状态；
- control-plane-only、fast/project、无限队列、总并发 6、写并发 2；
- 角色、模型、模板、assets/templates 分离和零本机绝对路径；
- init、upgrade、doctor、health、runtime_smoke、orchestrator 与新/旧/runtime 回归；
- 旧 evidence 兼容、health 并发一致快照、冒烟状态迁移、依赖、层级、所有权、心跳、超时、同因失败和新实例升级；
- README 中英繁本地链接和登记视觉资产；
- 官方 Skill validator 若存在则单独运行并保存真实输出。

任何未执行或失败项必须进入验证证据与残余风险，不得以源码检查代替运行结果。


## Goal boundary
- `goal_policy=explicit-only`; `control_plane_is_goal=false`; project control defaults to `controlled-auto`.
- A project task/long-lived domain task is not a Codex Goal. An active Goal reports `GOAL_MODE=unsupported_for_control_plane_setup` and is never reused or created by this Skill.
