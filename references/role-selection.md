# 角色与模型选择

| 角色 | 沙箱 | 档位 | 用途 |
|---|---|---|---|
| explorer / chore | read-only / write | Luna | 探索与低风险机械任务 |
| implementer / debugger / e2e-tester / evidence-researcher | 按角色 | Terra | 常规实现、调试、验证与证据 |
| architect / reviewer | read-only | Sol | 架构、安全、迁移升级与独立审查 |

模型映射可在初始化/升级时用 `--model-fast/standard/advanced` 覆盖，但必须运行实际冒烟验证订阅可用性。运行中不换模型；同因失败两次保存 handoff 并用新实例升级一档。high/critical 的 reviewer 永远是全新只读实例。
