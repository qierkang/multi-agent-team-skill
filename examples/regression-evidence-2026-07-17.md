# v1.0.0 生产级回归证据

- 日期：2026-07-17
- Skill 版本：`1.0.0`
- Harness 结构自检：`python3 scripts/health_check.py --deep`，结果 `STATE=skill_health_passed`
- 命令：`python3 scripts/regression_check.py`
- 总状态：`STATE=regression_passed; new=passed; existing=passed; runtime=passed`
- 优化模式复跑：`PYTHONOPTIMIZE=1 python3 scripts/regression_check.py`，同样通过，回归不依赖会被 `-O` 移除的 `assert`。
- 安装入口：`bash install/setup.sh`，结果 `STATE=setup_ready`。
- 同步入口：`bash install/sync.sh`，结果 `STATE=sync_plan_ready`；本次仅 dry-run，未写入用户级 Skill 目录。
- 官方 Skill 校验：`Skill is valid!`
- Python / JSON / TOML 解析：通过。

## 1.0.0 控制面升级

- `SKILL.md` 保持为小型路由入口，详细流程按需读取 `references/`。
- 可部署角色、项目协作文件和迁移报告统一迁入 `templates/`，作为单一事实来源。
- `assets/` 仅保留静态展示资产说明，不再混放执行模板。
- 新增主任务唯一控制面、按需长期任务和一次性子智能体三层结构。
- 新增 v2 registry、ownership locks、budget state、recovery journal、revision 与幂等登记。
- 受管 v1 非空任务可连续迁移；legacy marker 可升级；未知 schema 失败关闭。
- 健康检查覆盖心跳、所有权、并发写容量、Token 70/85/100、证据闸和派生状态漂移。

## 全新环境

验证 7 项：空目录路由、默认 dry-run 零写入、full 档案 8 个角色、安装清单、静态 doctor、Codex CLI 加载项目配置、重复安装转审计。

当前环境结果：`STATE=new_environment_regression_passed; checks=7`。如果目标环境未安装 Codex CLI，CLI 加载项会明确显示 `SKIP`，其余检查仍执行。

## 已有环境

验证 13 项：已有业务项目非侵入安装、受管 v1 非空任务事务升级、legacy marker、未知 schema 拦截、同名快照冲突、业务/配置/角色哈希保持、备份、Git ignore、符号链接、事务回滚和 doctor 漂移拒绝。

结果：`STATE=existing_environment_regression_passed; checks=13`。

## 运行时与故障注入

验证 10 项：跨进程锁、评分/模型路由、CAS revision、幂等、父子路径冲突、并发写容量、Token 70/85/100、证据完成闸、blocked 恢复再检查、locks/project token/snapshot 漂移恢复与路径穿越拒绝。

结果：`STATE=runtime_orchestration_regression_passed; checks=10`。

## 边界

以上是 Skill 源码包的确定性回归，证明生成和审计流程可以安全运行；每个真实目标项目仍需执行自身测试，并创建项目级 explorer 与全新 reviewer 验证实际模型、权限和工具可用性。

## 独立审查

- 第一轮干净上下文审查发现旧标记绕过、文件权限变化、doctor 漂移漏检和优化模式假阳性等问题，均已增加反例并修复。
- 修复后重新创建全新高级 reviewer，实际重跑普通与优化模式回归。
- v1.0 独立 reviewer 发现并推动修复非空任务迁移丢失、legacy marker、同名快照假成功、project token 漂移和 snapshot/registry 不等价。
- 最终只有在独立复核确认 High / Medium 阻塞项归零后才放行。
