# 角色选择与模型档位

## 核心角色

| 角色 | 权限 | 推理档位 | 用途 |
|---|---|---|---|
| explorer | read-only | Luna / low | 入口、调用链、文件所有权探索 |
| chore | workspace-write | Luna / low | 机械整理、格式化、低风险文档 |
| implementer | workspace-write | Terra / medium | 常规前后端实现与测试 |
| debugger | workspace-write | Terra / high | 故障复现、根因与最小修复 |
| architect | read-only | Sol / high | 架构、迁移、疑难决策与升级复盘 |
| reviewer | read-only | Sol / high | 新上下文独立审查、安全和回归 |

## 可选角色

| 角色 | 权限 | 推理档位 | 启用条件 |
|---|---|---|---|
| e2e-tester | workspace-write | Terra / medium | Web/UI、浏览器流程、截图回归 |
| evidence-researcher | read-only | Terra / medium | API、公开数据、证据链、供应商文档 |

## 档案

- `core`：通用软件项目，6 个核心角色。
- `web`：核心角色 + e2e-tester。
- `ai-data`：核心角色 + evidence-researcher。
- `full`：两类扩展都需要时使用。

## 动态升级

运行中的实例不能换脑。连续两次失败、架构边界不清或高风险发布时，保存任务包、diff、日志和测试结果，关闭旧实例，再用 architect/reviewer 创建干净实例。不要把失败历史无限堆入同一上下文。
