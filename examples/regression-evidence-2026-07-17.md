# 双环境回归证据

- 日期：2026-07-17
- Skill 版本：`0.2.0`
- Harness 结构自检：`python3 scripts/health_check.py --deep`，结果 `STATE=skill_health_passed`
- 命令：`python3 scripts/regression_check.py`
- 总状态：`STATE=regression_passed; new=passed; existing=passed`
- 优化模式复跑：`PYTHONOPTIMIZE=1 python3 scripts/regression_check.py`，同样通过，回归不依赖会被 `-O` 移除的 `assert`。
- 安装入口：`bash install/setup.sh`，结果 `STATE=setup_ready`。
- 同步入口：`bash install/sync.sh`，结果 `STATE=sync_plan_ready`；本次仅 dry-run，未写入用户级 Skill 目录。
- 官方 Skill 校验：`Skill is valid!`
- Python / JSON / TOML 解析：通过。

## 0.2.0 结构对齐

- `SKILL.md` 保持为小型路由入口，详细流程按需读取 `references/`。
- 可部署角色、项目协作文件和迁移报告统一迁入 `templates/`，作为单一事实来源。
- `assets/` 仅保留静态展示资产说明，不再混放执行模板。
- 新增 Skill 自身 `health_check.py`，并与目标项目 `team_doctor.py` 分工。
- 新增 `install/setup.sh`、`install/sync.sh`、`install/doctor.sh` 统一入口。
- 新增治理索引、健康清单及对应决策和风险闭环。

## 全新环境

验证 7 项：空目录路由、默认 dry-run 零写入、full 档案 8 个角色、安装清单、静态 doctor、Codex CLI 加载项目配置、重复安装转审计。

当前环境结果：`STATE=new_environment_regression_passed; checks=7`。如果目标环境未安装 Codex CLI，CLI 加载项会明确显示 `SKIP`，其余检查仍执行。

## 已有环境

验证 10 项：已有业务项目识别、dry-run 非侵入、业务文件与权限保持、原配置与 AGENTS 保留及备份、旧标记强制转审计、旧团队只读审计、父 Git ignore 门禁、深层符号链接阻断、完整事务回滚、doctor 拒绝模板漂移/额外角色/忽略文件/角色符号链接。

结果：`STATE=existing_environment_regression_passed; checks=10`。

## 边界

以上是 Skill 源码包的确定性回归，证明生成和审计流程可以安全运行；每个真实目标项目仍需执行自身测试，并创建项目级 explorer 与全新 reviewer 验证实际模型、权限和工具可用性。

## 独立审查

- 第一轮干净上下文审查发现旧标记绕过、文件权限变化、doctor 漂移漏检和优化模式假阳性等问题，均已增加反例并修复。
- 修复后重新创建全新高级 reviewer，实际重跑普通与优化模式回归。
- 最终结论：P0 / P1 / P2 均为 0，本地 Skill 功能验收可放行。
