# 完成闸

## 初始化/升级

- inspect 路由与实际动作一致，默认 dry-run 证据存在。
- manifest 与 project-state 为 Skill 2.0.0，control plane 为 `control-plane-only`。
- fast/project lane、无限队列、总并发 6、写并发 2 已声明；Codex `agents.max_depth=1`，registry 受管关系最多 depth 2。
- 角色、AGENTS 受管块、完整/最小派发包、台账、快照和 `.codex/team/*` 存在。
- 受管文件无 symlink、可追踪、schema 可解析，registry 与派生状态一致。
- v1/v2-upgrade 保留业务文件、线程 ID、状态和证据，且有备份。

## 运行态

- `team_doctor.py` 成功。
- `thread_orchestrator.py health` 成功；degraded 必须明确报告。
- manifest 冒烟状态只能是 `pending / partial_done / runtime_validation_done`；后两者必须由 `runtime_smoke.py` 记录真实、存在且非空的 explorer/reviewer 证据，证据不全不得标 done。
- 目标项目自身构建/测试已运行或明确说明无法运行。
- high/critical 使用 fresh reviewer；轻任务未被机械强制 full reviewer。
- completed 的所有证据路径均项目相对、存在、非空、非 symlink；失败两次使用新实例升级而非原地换模型。

## Skill 源码包

```bash
python3 scripts/health_check.py --deep
PYTHONOPTIMIZE=1 python3 scripts/regression_check.py
python3 scripts/check_readme_links.py
bash scripts/verify_assets.sh
```

若存在官方 validator，再运行并记录真实输出。任何未执行项必须列为残余风险，不得写成通过。
