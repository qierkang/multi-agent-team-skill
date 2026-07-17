# Multi-Agent Team Skill Agents Rules

## 定位

本 Skill 只维护多智能体研发团队的检查、初始化、审计、验证和模板，不承载业务项目代码。

## 强制规则

1. 修改目标项目前必须运行 `scripts/inspect_team.py` 并确认路由。
2. 新项目和已有项目初始化器默认 dry-run；只有用户明确要求落地时才使用 `--apply`。
3. 已有团队必须先运行 `team_audit.py`，不得直接覆盖 `.codex/agents`、`[agents.*]` 或安装清单。
4. 老项目不得调整业务源码、构建工具、技术栈和目录结构；只写受管协作文件。
5. 模板必须业务中性，不得包含客户名、业务项目名、本机绝对路径或凭据。
6. 变更角色资产后同步更新安装器、doctor、规则、治理记录和回归。
7. 完成前必须运行新环境、已有环境两套回归和官方 Skill 校验。

## 阅读顺序

1. `SKILL.md`
2. `references/INDEX.md`
3. 路由对应 workflow
4. `templates/role-catalog.json`
5. 修改或执行时再读 `scripts/`

## 输出边界

- Skill 维护产物只写入本目录。
- 项目协作产物只写入目标项目受管路径。
- 回归临时文件只写系统临时目录，并在结束后清理。
- `templates/` 是部署模板真源；`assets/` 只放静态展示资产。

## 作者

- `xyqierkang@gmail.com`
- `https://github.com/qierkang`
