# Registry / Snapshot Schema 2.0

每条记录至少包含：

```json
{
  "id": "TASK-001",
  "instance_id": "client-instance-id",
  "domain_key": "domain",
  "lane": "fast",
  "depth": 1,
  "parent_thread_id": null,
  "dependencies": [],
  "model_tier": "standard",
  "model": "gpt-5.6-terra",
  "status": "active",
  "owned_paths": ["src/domain"],
  "last_heartbeat": "ISO-8601",
  "timeout_seconds": 1800,
  "failure_history": [],
  "handoff_path": null,
  "generation": 1,
  "evidence_paths": []
}
```

队列记录 `instance_id=null`、`status=queued`、`generation=0`。运行中模型不可改；升级后新 ID 写入 `instance_id`，旧 ID 写入 `replaces_instance_id`。completed 必须有 evidence。状态快照的 `threads` 必须与 registry 完全一致。
