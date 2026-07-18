# Workflow: Existing Project

1. inspect 必须返回 `existing-project`，并记录 Git dirty 路径。
2. 只读识别技术信号与最小角色 profile，不改变技术栈、业务结构或构建工具。
3. dry-run `team_init.py`，检查 config 合并、AGENTS 受管块、备份与 Git ignored。
4. 冲突配置、同名不兼容协作文档或 symlink 路径失败关闭。
5. 用户明确要求安装后使用 `--apply`；只写受管协作文件。
6. 运行 doctor、health、项目测试和风险匹配的 reviewer。

现有业务文件、原有 AGENTS 内容、无关配置和文档必须保留；修改前备份到受管备份目录。
