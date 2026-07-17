# 任务快照结构

`team_audit.py --threads-json` 接受数组，或带 `threads` 数组的对象。

```json
{
  "schema_version": "2.0",
  "captured_at": "2026-07-17T00:00:00Z",
  "threads": [
    {
      "id": "task-id",
      "title": "前端实现",
      "status": "in_progress",
      "summary": "不超过10行的最近摘要",
      "evidence_paths": ["docs/协作/证据/task-id.md"],
      "owned_paths": ["src/pages/example.tsx"],
      "attempts": 1,
      "needs_user_input": false
    }
  ]
}
```

运行时注册表推荐状态：`provisioning`、`active`、`waiting_input`、`reviewing`、`degraded`、`completed`、`blocked`、`cancelled`、`archived`。审计器仍兼容 v1 `tasks` 与旧状态名，但只读兼容不等于已迁移。

缺少快照时，脚本仍可审计文件系统配置，但报告必须标记“运行时状态未核验”，不能推断任务已完成或失联。
