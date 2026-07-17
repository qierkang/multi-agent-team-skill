# Install

| 命令 | 作用 |
|---|---|
| `bash install/setup.sh` | 检查 Python 与 Skill 基础健康状态 |
| `bash install/sync.sh` | 只显示个人级 Skill 链接计划，不写入 |
| `bash install/sync.sh --apply` | 显式创建 Agents/Codex 个人级发现链接 |
| `bash install/doctor.sh` | 运行 Skill 健康检查和双环境深度回归 |

`sync.sh` 默认 dry-run，不覆盖普通目录；目标已存在且不是符号链接时会拒绝执行。
