# 新团队初始化工作流

## 1. Inspect

- 确认项目根目录，读取项目级 `AGENTS.md`、README/START-HERE、构建文件和 `git status`。
- 检查 `.codex/config.toml`、`.codex/agents/`、`docs/协作/` 与 `.gitignore`。
- 如果存在角色 TOML，停止并转 `$multi-agent-team` 审计模式，不能把升级伪装成初始化。

## 2. Select

- 依据 `role-selection.md` 选择最小档案。
- `auto` 只根据可验证的构建文件与目录信号选择，不根据项目名猜测。
- 模板数量不等于并发数量；即使安装 8 个角色，也最多同时运行 6 个实例。

## 3. Plan

```bash
python3 scripts/team_init.py --project <项目根目录> --profile auto
```

计划必须列出：选中档案、角色、将新增/修改/跳过的文件、配置冲突、ignored 路径和备份目录模式。

## 4. Apply

只有用户已明确要求执行，或确认 dry-run 计划后，才运行：

```bash
python3 scripts/team_init.py --project <项目根目录> --profile <档案> --apply
```

安装器只追加缺失制度，既有 `AGENTS.md` 用稳定标记包裹追加段；已有配置冲突默认阻断。

## 5. Verify

```bash
python3 scripts/team_doctor.py --project <项目根目录>
```

随后由主任务创建一个只读 explorer 和一个全新 reviewer 做最小真实冒烟：前者返回入口证据，后者只审查本次安装 diff 与 doctor 输出。无法执行真实子智能体时，状态只能是 `partial_done`。
