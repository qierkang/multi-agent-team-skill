# Multi-Agent Team Skill 2.0.4 验证证据

- 日期：2026-07-19
- 范围：AGENTS control-plane 冲突、真实主控绑定、strict 完成闸、跨 checkout/worktree 写入边界
- 结论：Skill 源码包、新环境、已有环境、运行时编排、优化模式和官方 Skill validator 全部通过

## 故障复现闭环

真实问题项目同时包含“快速直改/聚焦开发/主任务自行完成”和受管 `control-plane-only` 规则。修复前 doctor/health 均通过；修复后：

- `team_doctor.py` 输出 `STATE=static_validation_failed`，并列出 AGENTS 冲突行；
- 旧工作树 `team_upgrade.py` 输出 `STATE=upgrade_failed`，写入前阻断；
- 未对问题项目执行 apply、业务文件修改、提交或推送。

## 确定性回归

```text
python3 scripts/regression_control_plane_policy.py
STATE=control_plane_policy_regression_passed; checks=5

python3 scripts/regression_check.py
STATE=regression_passed; inspect=passed; new=passed; existing=passed; runtime=passed

python3 scripts/health_check.py --deep
PASS new and existing environment regression
PASS regressions pass with PYTHONOPTIMIZE=1
PASS deterministic title rename regression
PASS deterministic dispatch-return regression
STATE=skill_health_passed
```

聚合输出覆盖 58 个验收类别、222 个确定性 `require` 调用点，包括：

- 新项目与已有项目默认 dry-run、备份、回滚、ignored/symlink 安全；
- v1/v2 迁移、模型 replacement、runtime smoke 与真实 evidence；
- fast/project lane、无限队列、依赖、所有权、Token、超时与 blocked 恢复；
- AGENTS 冲突安装阻断、doctor/audit/upgrade 一致检测；
- control-task dry-run/应用、未确认 pin 拒绝、strict smoke/binding 门禁；
- 另一 checkout/worktree 写入停止条件。

## 官方与资产校验

```text
quick_validate.py .
Skill is valid!

python3 scripts/check_readme_links.py
PASS README local links and visual references; checked=49
STATE=readme_links_passed

bash scripts/verify_assets.sh .
PASS required asset: 5 files
PASS social preview under 1 MiB: 769546
STATE=asset_done
```

官方 validator 使用已存在且含 PyYAML 的隔离 Python 运行时；未修改全局依赖。

## 残余边界

- Python 仍不能从文件独立证明 Codex 客户端真的完成重命名、置顶或 Agent spawn；调用方必须保存真实客户端证据。
- AGENTS 冲突检测是确定性规则，不等于理解所有自然语言同义改写；未命中仍需 runtime smoke 和 fresh reviewer。
- 本轮只发布 Skill 2.0.4，没有自动修改存在大量未提交工作的业务项目。
