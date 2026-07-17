# Multi-Agent Team Skill

<!-- Keywords: multi-agent team, Codex multi-agent, AI agent orchestration, agent role templates, team initialization, legacy team audit, AGENTS.md generator, task ledger, clean-context review, skill health check, AI development workflow -->

<div align="center">
  <strong>为新项目部署研发团队 · 为既有项目安全升级协作层</strong>
  <br>
  <em>把多智能体研发从“维护常驻线程”升级为“模板库 + 台账 + 一次性实例”</em>
  <br><br>
  <code>SKILL.md</code>-format Skill，适用于 <strong>Codex</strong>、<strong>Claude Code</strong>、<strong>Cursor</strong> 等支持 Skill 的 AI 编程环境
  <br>
  <p>角色可替换、状态可外置、审查保持干净上下文</p>
</div>

<p align="center">
  <a href="./README.md">简体中文</a> · <a href="./docs/README_en.md">English</a>
</p>

<p align="center">
  <img src="./assets/social-preview.png?v=1" alt="Multi-Agent Team Skill：模板库、任务台账与独立审查" width="100%" />
</p>

<div align="center">
<a href="#快速开始">快速开始</a> · <a href="#工作流总览">工作流</a> · <a href="#角色与模型策略">角色与模型</a> · <a href="#系统架构">系统架构</a> · <a href="#命令参考">命令参考</a> · <a href="#常见问题">FAQ</a>

</div>

<div align="center">
[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.2.0-informational.svg?style=for-the-badge)](CHANGELOG.md)
[![Status](https://img.shields.io/badge/status-稳定可用-success.svg?style=for-the-badge)](#项目状态)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](scripts/)
[![Routes](https://img.shields.io/badge/routes-new_%7C_existing--project_%7C_existing--team-6F42C1.svg?style=for-the-badge)](#工作流总览)
[![Templates](https://img.shields.io/badge/templates-8_roles-orange.svg?style=for-the-badge)](#角色与模型策略)
[![Compatible](https://img.shields.io/badge/Compatible-Codex_%7C_Claude_Code_%7C_Cursor-blue.svg?style=for-the-badge)](#快速开始)

</div>

---

## 为什么需要 Multi-Agent Team Skill？

当一个项目开始使用多个 AI Agent，常见问题通常不是“少一个模型”，而是协作失控：

- 🧟 **常驻线程老化**：任务完成后仍保留上下文，后续审查被历史结论影响，出现僵尸线程。
- 🧠 **主线程膨胀**：主线程不断读取完整日志、长报告和失败过程，调度能力随上下文增长而下降。
- 🧩 **角色边界混乱**：探索、实现、调试、审查使用同一套上下文，文件所有权和验收责任不明确。
- 🔀 **老项目改造有风险**：为了部署团队模板而覆盖已有 `AGENTS.md`、配置或业务文件。
- ✅ **“已经完成”无法验证**：只看到口头摘要，没有初始化、审计、doctor 和双环境回归证据。

**Multi-Agent Team Skill 将这些问题收口为一套可执行制度：**

```text
$multi-agent-team 初始化当前项目团队
$multi-agent-team 审计并优化当前团队
$multi-agent-team 检查团队是否可用
```

| | |
|---|---|
| 🧭 **三路自动识别** | 先只读扫描目标目录，再选择新项目、已有业务项目或已有团队路径。 |
| 🛡️ **非侵入式安装** | 默认 dry-run；已有项目保留业务代码、配置和接手文档，只追加受管协作层。 |
| 🧱 **模板即制度** | 8 个角色 TOML、任务包、台账和迁移报告统一由 `templates/` 管理。 |
| 🔍 **干净上下文审查** | reviewer 每次为全新只读实例，只基于验收标准、最终 diff 与测试输出判断。 |
| 📋 **状态外置** | 完整产物落盘，子任务只回传短摘要与证据路径，主线程可随时接力。 |
| ✅ **可验证交付** | 自检、目标项目 doctor、新环境和已有环境回归组成完成闸。 |

---

## 项目概述

`multi-agent-team-skill` 是面向 AI 编程协作的团队编排 Skill。它不创建一支长期常驻的“虚拟团队”，而是在任务到来时根据项目状态和任务复杂度，部署合适的角色模板、生成可追溯的任务包和台账，并在任务结束后用独立审查和验证收口。

> **English summary**: `multi-agent-team-skill` is a `SKILL.md`-format orchestration skill for AI development teams. It safely initializes a reusable multi-agent collaboration layer for new or existing projects, keeps task state externalized, and uses fresh-context reviews plus deterministic regression checks to verify delivery.

## 核心特色

- **统一入口，按状态路由**：覆盖 `new`、`existing-project`、`existing-team`、`doctor` 和 `skill-health`。
- **一次性实例优先**：角色模板长期存在，执行实例任务完成即收口，避免上下文陈旧和线程僵尸化。
- **模型分级明确**：快速探索用 Luna，常规实现和调试用 Terra，架构决策与独立审查用 Sol。
- **模板与展示资产分离**：`templates/` 是可部署模板唯一真源；`assets/` 仅保存静态展示资产。
- **既有项目安全升级**：必须先 inspect；已有团队默认只审计并生成迁移报告，不自动覆盖或清场。
- **双层验证**：`health_check.py` 验证 Skill 源码包；`team_doctor.py` 验证目标项目安装结果。

## 与常见协作方式对比

| 方案 | 按项目状态自动路由 | 既有项目非侵入 | 独立审查 | 模板真源 | 双环境回归 |
|---|:---:|:---:|:---:|:---:|:---:|
| **Multi-Agent Team Skill** | ✅ | ✅ | ✅ 全新实例 | ✅ | ✅ |
| 固定常驻子线程 | ❌ | ⚠️ 依赖人工 | ⚠️ 容易受历史影响 | ❌ | ❌ |
| 手工复制角色配置 | ❌ | ⚠️ 容易覆盖 | ❌ | ⚠️ 易漂移 | ❌ |
| 单 Agent 串行执行 | 不适用 | ✅ | ⚠️ 自审偏差 | ❌ | ⚠️ 依赖人工 |

---

## 工作流总览

| 场景 | 路由 | 默认行为 | 交付物 |
|---|---|---|---|
| 🆕 **新项目** | `new` | 默认 dry-run，确认后安装协作层 | 角色模板、配置片段、AGENTS 受管块、任务台账与任务包 |
| 🔧 **已有业务项目** | `existing-project` | 非侵入式补齐协作层并保留备份 | 安装清单、备份记录、静态 doctor 结果 |
| 🔍 **已有团队** | `existing-team` | 只读审计，不自动迁移或关闭旧任务 | 团队迁移报告、风险与建议 |
| 🩺 **安装质量检查** | `doctor` | 只读校验配置、角色、权限和符号链接 | `STATE=static_validation_done` 或明确失败项 |
| 🧪 **Skill 自检** | `skill-health` | 验证 Skill 源码包和深度回归 | `STATE=skill_health_passed` |

> **不确定走哪条路？** 先运行 `python3 scripts/inspect_team.py --project <项目根目录>`，不得仅凭项目名称或目录猜测。

---

## 快速开始

### 前置条件

- 支持 `SKILL.md` 的 AI 编程环境，例如 Codex、Claude Code、Cursor。
- Python 3.11+（使用标准库 `tomllib` 解析配置）。
- Bash（用于 `install/` 下的安装与 doctor 入口）。

### 作为 Skill 使用

```text
$multi-agent-team 初始化当前项目团队
$multi-agent-team 审计并优化当前团队
$multi-agent-team 检查团队是否可用
```

### 直接调用脚本

```bash
# 1. 先识别目标项目状态（只读）
python3 scripts/inspect_team.py --project <项目根目录>

# 2. 新项目或已有业务项目：先预览，不写文件
python3 scripts/team_init.py --project <项目根目录> --profile auto

# 3. 用户确认后才真正安装
python3 scripts/team_init.py --project <项目根目录> --profile auto --apply

# 4. 已有团队：只读审计，生成迁移建议
python3 scripts/team_audit.py --project <项目根目录>

# 5. 校验目标项目安装质量
python3 scripts/team_doctor.py --project <项目根目录>
```

### 安装到本机 Skill 目录

```bash
# 先检查当前 Skill 源码包
bash install/setup.sh

# 只输出链接计划，不写入目录
bash install/sync.sh

# 明确确认后才创建符号链接
bash install/sync.sh --apply
```

---

## 角色与模型策略

### 角色档案

| 档案 | 使用场景 | 包含角色 |
|---|---|---|
| `core` | 常规研发项目 | explorer、chore、implementer、debugger、architect、reviewer |
| `web` | 有浏览器交互或前端验收 | core + e2e-tester |
| `ai-data` | API、公开数据、证据链或模型集成 | core + evidence-researcher |
| `full` | 同时需要 Web 与 AI/数据能力 | 全部 8 个角色；实际并发仍不超过 6 |

### 模型与权限边界

| 层级 | 模型 | 典型角色 | 使用原则 |
|---|---|---|---|
| 快速 | `gpt-5.6-luna` | explorer、chore | 只读探索、机械整理、低风险明确任务 |
| 标准 | `gpt-5.6-terra` | implementer、debugger、e2e-tester、evidence-researcher | 明确任务包内的实现、调试、验证和证据核验 |
| 高级 | `gpt-5.6-sol` | architect、reviewer | 架构决策、疑难升级、独立审查；reviewer 保持全新只读上下文 |

**运行规则：**

- 默认 `max_threads = 6`，`max_depth = 1`，同时写代码的实例最多 2 个。
- 不在运行中的实例内切换模型；需要升级时保留证据和现场，重新创建更高层级实例。
- 子任务完整产物必须外置；返回主线程的摘要不超过 10 行，并附证据路径。

---

## 系统架构

![Multi-Agent Team Skill 中文编排总览](./assets/architecture/zh-CN/team-orchestration-overview.png)

```text
用户需求 / 项目路径
        ↓
SKILL.md（最小触发规则与路由）
        ↓
scripts/inspect_team.py（只读识别项目状态）
        ↓
┌──────────────────┬──────────────────────┬────────────────────┐
│ new              │ existing-project     │ existing-team      │
│                  │                      │                    │
│ team_init.py     │ team_init.py         │ team_audit.py      │
│ dry-run -> apply │ non-invasive install │ read-only report   │
└──────────────────┴──────────────────────┴────────────────────┘
        ↓
templates/（角色、台账、任务包、配置和迁移报告真源）
        ↓
team_doctor.py（目标项目静态校验）
        ↓
目标项目 explorer / reviewer 运行态冒烟
        ↓
任务台账 + 摘要 + 证据路径 + 可接手状态
```

### 架构说明

- `SKILL.md` 只保存触发条件、路由和不可违背的约束，避免把详细制度塞入每一次会话上下文。
- `references/` 按路由提供工作流和规则，任务只读取当前需要的文档。
- `templates/` 提供唯一可部署内容；脚本不再从 `assets/` 读取执行模板。
- `governance/` 记录设计决策、风险、变更和维护者健康检查要求。
- `install/` 只负责本机安装入口；`sync.sh` 默认 dry-run，显式 `--apply` 才能写入符号链接。

### 既有团队的安全升级

![既有项目安全升级流程](./assets/architecture/zh-CN/safe-existing-skill-upgrade.png)

先审计现状，再输出迁移报告；只有用户明确确认后才会写入受管协作层。该流程不会覆盖业务源码、删除既有角色或静默关闭任务。

---

## 目录结构

```text
multi-agent-team-skill/
├── SKILL.md                          # 触发入口与最小路由规则
├── START-HERE.md                     # 首次接手导航
├── README.md                         # 本文档
├── AGENTS.md                         # Codex 接手规则
├── CLAUDE.md                         # Claude / 通用 Agent 接手规则
├── templates/                        # 部署模板唯一真源
│   ├── agents/                       # 8 个角色 TOML
│   ├── project/                      # AGENTS 块、配置和任务文档模板
│   ├── reports/                      # 团队迁移报告模板
│   └── role-catalog.json             # 角色、档案与模型层级目录
├── scripts/                          # inspect / init / audit / doctor / regression
├── install/                          # setup / sync / doctor 统一入口
├── references/                       # 按路由渐进加载的详细制度
├── examples/                         # 请求示例和回归证据
├── assets/                           # 仅静态展示资产
└── governance/                       # 决策、风险、变更与健康标准
```

---

## 命令参考

| 命令 | 说明 |
|---|---|
| `python3 scripts/inspect_team.py --project <path>` | 只读识别目标状态并输出推荐路由 |
| `python3 scripts/team_init.py --project <path> --profile auto` | 默认 dry-run，预览安装计划 |
| `python3 scripts/team_init.py --project <path> --profile auto --apply` | 用户确认后写入受管协作层 |
| `python3 scripts/team_audit.py --project <path>` | 审计已有团队并生成非覆盖式迁移报告 |
| `python3 scripts/team_doctor.py --project <path>` | 校验目标项目的配置、角色、权限和受管文件 |
| `python3 scripts/health_check.py` | 校验当前 Skill 源码包结构和模板完整性 |
| `python3 scripts/health_check.py --deep` | 在自检基础上执行新环境与已有环境真实派生回归 |
| `python3 scripts/regression_check.py` | 汇总执行双环境回归 |
| `bash install/setup.sh` | 运行 Skill 快速自检并确认本机依赖 |
| `bash install/sync.sh [--apply]` | 输出或执行本机 Skill 链接同步；默认不写入 |
| `bash install/doctor.sh` | 执行当前 Skill 的深度健康检查 |

## 功能模块

| 模块 | 解决的问题 | 核心产物 |
|---|---|---|
| 项目识别 | 不凭目录名猜测新旧状态 | 路由结论与检查证据 |
| 团队初始化 | 将一次性实例制度落到目标项目 | 配置片段、角色模板、任务台账 |
| 既有团队审计 | 防止覆盖和线程僵尸化 | 迁移报告、风险项与建议 |
| 安装 Doctor | 检查角色、权限、链接和受管文件漂移 | `STATE=static_validation_done` |
| 回归验证 | 用真实派生环境证明脚本仍可用 | 新环境、已有环境回归证据 |

## 技术栈

- **运行时**：Python 3.11+ 标准库；不依赖第三方 Python 包。
- **安装入口**：Bash，默认只读 / dry-run，显式 `--apply` 才会写入。
- **配置格式**：TOML、JSON、Markdown；模板可读、可审计、可版本化。
- **质量门禁**：静态健康检查、双环境回归、Python 优化模式复跑与本地链接检查。

---

## 开发与验证

### 开发指南

1. 先修改 `templates/` 中的唯一真源，不直接编辑目标项目的生成结果。
2. 同步更新对应脚本、路由规则与治理记录；角色和模型变化还必须更新 `role-catalog.json`。
3. 先跑静态检查，再跑新环境与已有环境回归；未通过不得更新“稳定可用”状态。
4. 公开发布前执行 [`references/github-publish.md`](./references/github-publish.md) 的安全扫描、社区文件和资产校验。

### 修改边界

| 需要修改什么 | 优先位置 |
|---|---|
| 触发条件、路由或硬约束 | `SKILL.md` |
| 详细工作流和协作制度 | `references/` |
| 角色、配置、台账或迁移报告 | `templates/` |
| 自动化行为和安全边界 | `scripts/` 或 `install/` |
| 变更理由、开放风险或验收规则 | `governance/` |

### 验证步骤

```bash
# 1. Skill 静态健康检查
python3 scripts/health_check.py

# 2. 全量自检：包含新环境和已有环境派生回归
python3 scripts/health_check.py --deep

# 3. 防止测试依赖 Python assert 的优化模式复跑
PYTHONOPTIMIZE=1 python3 scripts/regression_check.py

# 4. 官方 Skill 格式校验（如本机已安装校验器）
python3 <skill-validator>/quick_validate.py .
```

只有静态检查、双环境回归和目标项目运行态验证均通过，才可以报告“团队已就绪”。

---

## 常见问题

### 需要每次都启动 8 个角色吗？

不需要。`core` 是默认档案；只有浏览器验收时增加 `e2e-tester`，只有 API、公开数据或证据链任务时增加 `evidence-researcher`。模板数量不等于同时运行数量。

### 已有项目会被重构或覆盖吗？

不会。必须先运行 `inspect_team.py`。已有业务项目默认 dry-run，安装时只追加受管协作层并保留备份；已有团队只会进入审计路径，不会自动迁移、删除或关闭旧任务。

### 为什么 reviewer 不能复用实现线程？

独立审查需要避免开发过程中的路径依赖。reviewer 必须是全新、只读上下文，只看任务验收标准、最终 diff 和测试输出。

### `health_check.py` 与 `team_doctor.py` 有什么区别？

前者验证本 Skill 的源码、模板和回归；后者验证某个目标项目的实际安装结果。两者不能互相替代。

---

## 🚦 项目状态

- 当前状态：`稳定可用`
- 版本阶段：`0.2.0`
- 默认协作模型：`模板库 + 台账 + 一次性实例`
- 兼容范围：`Python 3.11+ · Bash · Codex / Claude Code / Cursor`
- 角色与模型真源：[`templates/role-catalog.json`](./templates/role-catalog.json)
- 变更、风险与健康标准：[`governance/`](./governance/)
- 回归证据：[`examples/regression-evidence-2026-07-17.md`](./examples/regression-evidence-2026-07-17.md)

## 参与贡献

欢迎提交问题、场景建议或可复现的修复。提交前请阅读 [贡献指南](./CONTRIBUTING.md)，并至少运行：

```bash
python3 scripts/health_check.py --deep
PYTHONOPTIMIZE=1 python3 scripts/regression_check.py
bash scripts/verify_assets.sh .
```

请不要提交真实密钥、客户项目名、绝对本机路径、生成缓存或未经证实的平台兼容性声明。

## 版本说明

当前版本为 `0.2.0`。版本变更与兼容性说明见 [CHANGELOG.md](./CHANGELOG.md)。发布时遵循语义化版本：破坏性变更升主版本，新增兼容能力升次版本，修复升补丁版本。

## 致谢

本 Skill 采用 Harness Engineering 的实践：模板成为真源、运行状态外置、审查保持干净上下文，并以确定性验证替代口头完成声明。

## Star History

首次公开仓库创建并推送后，再添加真实的 Star History 图表；在此之前不伪造仓库链接或星标数据。发布步骤见 [GitHub 发布清单](./references/github-publish.md)。

## 许可证

本项目以 [MIT License](./LICENSE) 发布。

## 作者

- `xyqierkang@gmail.com`
- <https://github.com/qierkang>
