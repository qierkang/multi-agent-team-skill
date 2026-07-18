# Multi-Agent Team Skill v2 验证证据

- 日期：2026-07-18
- Skill：`multi-agent-team` 2.0.0
- 状态：发布阻断修复后的确定性源码包验证通过；官方 validator 与真实客户端 Agent 冒烟见残余风险。

## 真实命令与结果

### 深度健康检查

```bash
python3 scripts/health_check.py --deep
```

- 退出码：`0`
- 最终状态：`STATE=skill_health_passed`
- 包含：Python 编译、模板/生成器一致性、零本机绝对路径、视觉资产、README 链接、普通回归和优化模式回归。

### Deterministic regressions

深度健康检查实际运行并通过以下状态：

```text
STATE=inspect_routes_regression_passed; checks=4
STATE=new_environment_regression_passed; checks=11
STATE=existing_environment_regression_passed; checks=16
STATE=runtime_orchestration_regression_passed; checks=17
STATE=regression_passed; inspect=passed; new=passed; existing=passed; runtime=passed
```

四套脚本共输出 **48 个聚合验收类别**（`passed.append(...)` 静态调用点），AST 可复核统计为 **167 个 `require(...)` 静态调用点**。统计命令：

```bash
python3 - <<'PY'
import ast
from pathlib import Path
files = [Path(f"scripts/regression_{name}.py") for name in (
    "inspect_routes", "new_environment", "existing_environment", "runtime_orchestration"
)]
print(sum(
    isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "require"
    for path in files for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
))
PY
```

覆盖 inspect、init、upgrade、doctor、health、队列、依赖、并发、所有权、层级、心跳/Token、同因失败、新实例升级以及最终审查的四个 P1。

此前三项阻断回归仍保持通过：

```text
PASS audit accepts completed-task evidence and evidence_paths without false missing-evidence advice
PASS health waits on the runtime lock and reads one consistent registry/derived-state snapshot
PASS runtime smoke moves pending to partial/done only with real role evidence and doctor enforcement
```

health 回归不是概率轮询：writer 在 runtime lock 内先写新 registry、故意暂停派生文件同步；回归确认 health 在锁释放前保持阻塞，writer 同步 locks/budget/snapshot 后 health 返回 `STATE=runtime_health_passed`。旧实现会在同一场景稳定返回三类 drift。

runtime smoke 回归验证了默认 dry-run 零写入、缺失文件失败关闭、单侧 explorer 证据只能到 `partial_done`、补 fresh reviewer 证据才到 `runtime_validation_done`，以及删除已登记证据后 doctor 必须失败。回归使用隔离临时项目中的非空测试日志，**不是**真实 Codex 客户端冒烟通过声明。

### 最终审查四个 P1 的闭环

```text
PASS existing v2 mode upgrade enables controlled-auto while active model changes require replacement
PASS managed v1 migration requires real evidence and refuses in-place active model changes
PASS completion, health and doctor reject absolute, traversal, missing, empty and symlink evidence
PASS blocked recovery rechecks dispatch, handoff, dependencies, domain, ownership and capacity
```

- v2 模型重配置在 runtime lock 内检查活动/可恢复实例；发现实例时输出 `STATE=replacement_required`，回归逐文件哈希确认 registry、snapshot、manifest、project-state 和角色模板均零写入。v1 active 迁移采用同一拒绝边界。
- `validate_evidence_path(s)` 是 audit、update、v1/v2 migration、doctor、health 和 runtime smoke 的共享口径；正向回归先创建真实非空文件，反向覆盖绝对路径、`..`、不存在、空文件和 symlink。
- 默认 recommend 的受管 v2 团队经 `team_upgrade.py --thread-mode controlled-auto --apply` 后，manifest/project-state 同步，doctor 通过且 project task enqueue/dispatch 成功；外部动作策略仍为 `explicit-user-approval`。
- `queued -> blocked -> active` 两步绕过被拒绝且 registry 字节不变；合法 blocked 恢复必须已有 instance/start/dispatch metadata、真实 handoff，并重过依赖、父任务、模式、domain、所有权和 6/2 容量门禁。

### Python optimize

除 `health_check.py --deep` 内置的优化模式复跑外，还单独执行了用户要求的命令：

```bash
PYTHONOPTIMIZE=1 python3 scripts/regression_check.py
```

- 退出码：`0`
- 四套回归真实状态：

```text
STATE=regression_passed; inspect=passed; new=passed; existing=passed; runtime=passed
```

因此验证不依赖会被 `-O` 移除的 `assert`。

### README 与视觉资产

```bash
python3 scripts/check_readme_links.py
bash scripts/verify_assets.sh
```

真实状态：

```text
PASS README local links and visual references; checked=49
STATE=readme_links_passed
PASS social preview under 1 MiB: 769546
STATE=asset_done
```

中英文 README 引用的 5 个正式图片都在 `assets/asset-manifest.json` 登记，并带 `image_gen` provenance；部署模板仍只来自 `templates/`。

### 官方 Skill validator

本轮重新探测后发现 Anthropic Agent Skills 插件内的 validator，并执行：

```bash
python3 ~/.claude/plugins/marketplaces/anthropic-agent-skills/skills/skill-creator/scripts/quick_validate.py .
```

- 首次运行退出码：`1`
- 首次失败：`ModuleNotFoundError: No module named 'yaml'`

随后使用 Codex bundled Python，并将 PyYAML 安装到临时 `/tmp` target 隔离目录后重跑；退出码：`0`，最终真实输出：`Skill is valid!`。全程未修改全局 Python 环境，也未伪造官方 validator 通过证据。内置 frontmatter/name/version 校验同样通过。

## 已验证的不变量

- 主任务 planner 无 `handle_in_main` / `use_subagents` 路由，默认 `control-plane-only`。
- fast lane 普通任务一次性派发；project lane 长期任务最多再派一层一次性 Agent。
- Codex 项目配置保持 `agents.max_depth=1`；registry depth 2 是主控制面代 project task 管理 one-shot 的跨任务关系，回归拒绝更深层级。
- 队列至少回归入队 12 个待执行项且不受活跃容量限制；活跃总并发 6、写并发 2。
- high risk 返回 `always-fresh-reviewer`；轻任务返回 minimal packet + `on-failure`。
- 同因失败两次保留原 Terra 实例 ID，之后只允许新 Sol 实例通过 handoff 接替。
- schema 1.0 和 Skill 1.0.1 受管团队均确定升级到 2.0.0；旧 `evidence` 字段仅在指向项目内真实非空普通文件时保留。
- 受管 v2 的显式 recommend -> controlled-auto 更新已由 doctor 和真实 project enqueue/dispatch 回归覆盖。
- 未升级旧团队的只读 audit 同时识别 `evidence` 与 `evidence_paths`，已完成且有旧证据的任务不再误报缺证据。
- 新项目、已有项目、已有团队、未知 schema、ignored 路径和 symlink 逃逸均有回归。

## 未验证/残余风险

- 临时回归环境没有调用真实 Codex 客户端创建 Agent；`runtime_smoke.py` 状态机已验证，但具体订阅中的 Luna/Terra/Sol entitlement、沙箱、工具权限和证据真实性仍需每个目标项目冒烟。无法执行时必须保持 `pending`，只完成一个角色时保持 `partial_done`。
- 现有视觉图片沿用已登记的 image_gen 资产，只验证引用和 provenance，没有为 2.0.0 重新生成视觉内容。
