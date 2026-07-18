# Multi-Agent Team Skill v2

<p align="center">
  <a href="../README.md">简体中文</a> · <a href="./README_zh-tw.md">繁體中文</a> · <a href="./README_en.md">English</a>
</p>

<p align="center"><img src="../assets/social-preview.png?v=2" alt="Multi-Agent Team Skill" width="100%" /></p>

2.0.0 將主任務預設為唯一 `control-plane-only` 控制面：只做唯讀判斷、拆分、排隊、派發、監控、驗收、彙報與受管調度狀態寫入，不修改生產程式碼。

## Inspect-first

使用者只需說「用 multi-agent-team-skill 初始化／升級／檢查這個專案」，不需選擇 orchestrator、lane 或 schema。

```bash
python3 scripts/inspect_team.py --project <專案根目錄>
```

| 自動路由 | 安全預設 |
|---|---|
| `new` | dry-run 初始化 |
| `existing-project` | 非侵入 dry-run 安裝 |
| `existing-team:v1` | 確定性遷移至 schema 2.0 |
| `existing-team:v2-upgrade` | 事務升級受管 1.x 團隊至 2.0.0 |
| `existing-team:v2` | doctor 與 runtime health |
| `existing-team:audit` | 唯讀審計；未知 schema 失敗關閉 |

## 雙通道

| 通道 | 任務 | 生命週期 | 派發與審查 |
|---|---|---|---|
| fast lane | 一般、短時、邊界明確 | 一次性 Agent，完成釋放 | 輕任務最小包，預設失敗時審查 |
| project lane | 跨日、持續、獨立領域 | 建立或複用長期領域任務 | 完整包；高風險 fresh reviewer |

固定層級為「主任務控制面 -> project 長期任務 -> 一次性 Agent」，禁止更深巢狀。隊列數量不限，執行總併發預設 6、寫實例 2。依賴、路徑所有權、心跳、逾時、狀態、交接與證據都外置於 `.codex/team/`。

## 模型與失敗升級

- Luna：快速探索與輕量機械工作。
- Terra：一般實作、除錯與測試。
- Sol：架構、安全、遷移與全新獨立審查。

執行中的實例不得換腦。同一異常指紋連續失敗兩次後，保存 handoff、停止舊實例，再以更高檔模型建立新實例；`replace` 記錄 generation 與 `replaces_instance_id`。

輕任務使用[最小派發包](../templates/project/docs/最小派发包.template.md)，失敗或範圍擴大後切換[完整任務包](../templates/project/docs/任务包.template.md)。高風險與 critical 任務始終使用全新唯讀 reviewer。

## 指令

```bash
python3 scripts/inspect_team.py --project <path>
python3 scripts/team_init.py --project <path> --profile auto
python3 scripts/team_upgrade.py --project <path>
python3 scripts/team_upgrade.py --project <path> --thread-mode controlled-auto --apply
python3 scripts/team_doctor.py --project <path>
python3 scripts/thread_orchestrator.py health --project <path>
python3 scripts/runtime_smoke.py --project <path> --explorer-evidence artifacts/explorer-smoke.log --apply
python3 scripts/runtime_smoke.py --project <path> --reviewer-evidence artifacts/reviewer-smoke.log --apply

python3 scripts/thread_orchestrator.py plan --project <path> --task-json task.json
python3 scripts/thread_orchestrator.py enqueue --project <path> --task-json task.json --task-id TASK-001 --apply
python3 scripts/thread_orchestrator.py dispatch --project <path> --task-id TASK-001 --instance-id <id> --apply
```

Codex 專案設定固定 `agents.max_depth=1`；registry depth 2 只是主任務控制面代 project task 派發 one-shot 的受管關係，不是 Agent 遞迴建立 Agent。沒有真實客戶端輸出時保持 `pending`；單側角色非空證據只能到 `partial_done`，explorer 與 fresh reviewer 都有證據才到 `runtime_validation_done`。

受管 v2 團隊明確使用 `--thread-mode controlled-auto` 時，manifest 與 project-state 必須同步更新，但外部發布、生產寫入、付費動作與憑據變更仍需獨立批准。模型重配置遇到活動或可恢復實例時必須零寫入並輸出 `replacement_required`。所有完成與冒煙 evidence 必須是專案相對、無 `..`、存在、非空且非 symlink 的檔案；blocked 恢復還必須具備既有 dispatch metadata、真實 handoff，並重新通過依賴、所有權與容量門禁。

初始化與升級預設 dry-run；只有明確要求落地才使用 `--apply`。既有專案保留業務程式碼、建置工具、技術棧、原有文件與無關設定。未知 schema、自訂受管角色漂移、符號連結逃逸、ignored 受管路徑和設定衝突都失敗關閉。

## 驗證

```bash
python3 scripts/health_check.py --deep
PYTHONOPTIMIZE=1 python3 scripts/regression_check.py
python3 scripts/check_readme_links.py
bash scripts/verify_assets.sh
```

深度閘門涵蓋 inspect、init、upgrade、doctor、health、orchestrator、新／既有／runtime 回歸、最佳化 Python、README 連結與視覺資產。若本機存在官方 Skill validator，再執行其 `quick_validate.py`。

- [v2 驗證證據](../examples/regression-evidence-2026-07-18-v2.md)
- [生產評分卡](../governance/PRODUCTION-SCORECARD.md)
- [References 索引](../references/INDEX.md)
- [CHANGELOG](../CHANGELOG.md)

`templates/` 是部署真源，`assets/` 僅保存靜態展示資產。模板不得含客戶名、業務專案名、本機絕對路徑或憑據。外部發布、生產寫入、付費動作與憑據變更必須單獨明確批准。

作者：`xyqierkang@gmail.com` · [GitHub](https://github.com/qierkang)
