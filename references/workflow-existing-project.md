# 已有业务项目工作流

适用于项目中已经存在源码、文档、Git 历史或项目规则，但尚未部署项目级多智能体角色的场景。

## 步骤

1. 运行 `inspect_team.py`，确认路由是 `existing-project`，并记录 Git 根目录与脏文件数量。
2. 读取项目自身的 `AGENTS.md`、`START-HERE.md`、`README.md` 和任务相关入口，不扫描依赖与构建产物。
3. 先运行 `team_init.py` dry-run，检查角色档案、配置冲突、被忽略路径和将追加的文件。
4. 默认只追加受管协作块，保留原 `.codex/config.toml`、`AGENTS.md` 和业务文件；修改前建立项目内备份。
5. 用户确认计划后才执行 `--apply`。存在冲突时默认阻断，不能用 `--replace-conflicts` 猜测用户意图。
6. 运行 `team_doctor.py`，然后执行目标项目自己的构建、测试以及 explorer/reviewer 运行态冒烟。

## 禁止动作

- 不重写已有 AGENTS 正文。
- 不删除已有文档、脚本或业务配置。
- 不因为项目位于父级 Git 仓库而忽略父级 `.gitignore`。
- 不把静态 doctor 通过描述成真实子智能体已经可运行。
