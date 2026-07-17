# Multi-Agent Team Skill

<!-- Keywords: multi-agent team, Codex multi-agent, AI agent orchestration, agent role templates, team initialization, legacy team audit, AGENTS.md generator, task ledger, clean-context review, skill health check, AI development workflow -->

<div align="center">
  <strong>為新專案部署研發團隊 · 為既有專案安全升級協作層</strong>
  <br>
  <em>主任務統一調度長期任務與一次性子智能體，可偵測、可復原、可節省 Token</em>
  <br><br>
  <code>SKILL.md</code> 格式的 Skill，適用於 <strong>Codex</strong>、<strong>Claude Code</strong>、<strong>Cursor</strong> 等支援 Skill 的 AI 程式設計環境
  <br>
  <p>角色可替換、狀態可外置、審查保持乾淨上下文</p>
</div>

<p align="center">
  <a href="../README.md">简体中文</a> · <a href="./README_zh-tw.md">繁體中文</a> · <a href="./README_en.md">English</a>
</p>

<p align="center">
  <img src="../assets/social-preview.png?v=1" alt="Multi-Agent Team Skill：模板庫、任務台賬與獨立審查" width="100%" />
</p>

<div align="center">
<a href="#快速開始">快速開始</a> · <a href="#工作流總覽">工作流</a> · <a href="#角色與模型策略">角色與模型</a> · <a href="#系統架構">系統架構</a> · <a href="#指令參考">指令參考</a> · <a href="#常見問題">FAQ</a>
</div>

<p align="center">
  <a href="../LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="License" /></a>
  <a href="../CHANGELOG.md"><img src="https://img.shields.io/badge/version-1.0.1-informational.svg?style=for-the-badge" alt="Version" /></a>
  <a href="#專案狀態"><img src="https://img.shields.io/badge/status-穩定可用-success.svg?style=for-the-badge" alt="Status" /></a>
  <a href="../scripts/"><img src="https://img.shields.io/badge/Python-3.11%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python" /></a>
  <a href="#快速開始"><img src="https://img.shields.io/badge/Compatible-Codex_%7C_Claude_Code_%7C_Cursor-blue.svg?style=for-the-badge" alt="Compatible" /></a>
</p>

---

## 為什麼需要 Multi-Agent Team Skill？

當一個專案開始使用多個 AI Agent，常見問題通常不是「少一個模型」，而是協作失控：

- 🧟 **常駐執行緒老化**：任務完成後仍保留上下文，後續審查被歷史結論影響，出現殭屍執行緒。
- 🧠 **主執行緒膨脹**：主執行緒不斷讀取完整日誌、長報告與失敗過程，調度能力隨上下文成長而下降。
- 🧩 **角色邊界混亂**：探索、實作、除錯、審查共用同一套上下文，檔案所有權與驗收責任不明確。
- 🔀 **舊專案改造有風險**：為了部署團隊模板而覆寫既有 `AGENTS.md`、設定或業務檔案。
- ✅ **「已經完成」無法驗證**：只看到口頭摘要，缺少初始化、升級、doctor 與執行期回歸證據。

**Multi-Agent Team Skill 把這些問題收斂為一套可執行制度：**

```text
$multi-agent-team 初始化當前專案團隊
$multi-agent-team 稽核並最佳化當前團隊
$multi-agent-team 檢查團隊是否可用
```

| | |
|---|---|
| 🧭 **三路自動識別** | 先唯讀掃描目標目錄，再選擇新專案、既有業務專案或既有團隊路徑。 |
| 🛡️ **非侵入式安裝** | 預設 dry-run；既有專案保留業務程式碼、設定與接手文件，只追加受管協作層。 |
| 🧱 **模板即制度** | 8 個角色 TOML、任務包、台賬與遷移報告統一由 `templates/` 管理。 |
| 🔍 **乾淨上下文審查** | reviewer 每次為全新唯讀實例，只依驗收標準、最終 diff 與測試輸出判斷。 |
| 📋 **狀態外置** | 長期任務、路徑鎖、Token 預算與復原日誌落在 `.codex/team/`，主任務只消費短摘要。 |
| 🩺 **健康與復原** | 偵測失聯心跳、重複領域、所有權衝突、狀態漂移與 Token 超限，支援 reconcile。 |
| ✅ **可驗證交付** | 自檢、目標專案 doctor、新／舊環境與執行期故障回歸組成完成閘。 |

---

## 專案概述

`multi-agent-team-skill` 是面向 AI 程式設計協作的受控編排 Skill。使用者只需使用主任務：主任務依評分決定直接執行、派生一次性子智能體，或建立／複用具獨立模型與邊界的長期任務。長期任務可繼續使用一次性子智能體，但不能再建立長期任務。

> **English summary**: `multi-agent-team-skill` is a `SKILL.md`-format orchestration skill for AI development teams. It safely initializes a reusable multi-agent collaboration layer for new or existing projects, keeps task state externalized, and uses fresh-context reviews plus deterministic regression checks to verify delivery.

## 核心特色

- **統一入口，依狀態路由**：涵蓋 `new`、`existing-project`、`existing-team`、`doctor` 與 `skill-health`。
- **三層受控結構**：主任務 → 按需長期任務 → 一次性子智能體；預設只推薦，顯式開啟後才自動建立。
- **模型分級明確**：快速探索用 Luna，常規實作與除錯用 Terra，架構決策與獨立審查用 Sol。
- **模板與展示資產分離**：`templates/` 是可部署模板唯一真源；`assets/` 僅保存靜態展示資產。
- **既有專案安全升級**：v1 受管團隊支援交易式升級到 v2；未知 schema 仍 fail-closed 並轉唯讀稽核。
- **Token 與異常閘門**：70% 壓縮、85% 凍結範圍、100% 停止；同因兩次失敗後升級。
- **雙層驗證**：`health_check.py` 驗證 Skill 源碼包；`team_doctor.py` 驗證目標專案安裝結果。

## 與常見協作方式對比

| 方案 | 依專案狀態自動路由 | 既有專案非侵入 | 獨立審查 | 模板真源 | 三類回歸 |
|---|:---:|:---:|:---:|:---:|:---:|
| **Multi-Agent Team Skill** | ✅ | ✅ | ✅ 全新實例 | ✅ | ✅ |
| 固定常駐子執行緒 | ❌ | ⚠️ 依賴人工 | ⚠️ 容易受歷史影響 | ❌ | ❌ |
| 手工複製角色設定 | ❌ | ⚠️ 容易覆寫 | ❌ | ⚠️ 易漂移 | ❌ |
| 單 Agent 串行執行 | 不適用 | ✅ | ⚠️ 自審偏差 | ❌ | ⚠️ 依賴人工 |

---

## 工作流總覽

| 場景 | 路由 | 預設行為 | 交付物 |
|---|---|---|---|
| 🆕 **新專案** | `new` | 預設 dry-run，確認後安裝協作層 | 角色模板、設定片段、AGENTS 受管區塊、任務台賬與任務包 |
| 🔧 **既有業務專案** | `existing-project` | 非侵入式補齊協作層並保留備份 | 安裝清單、備份紀錄、靜態 doctor 結果 |
| 🔍 **受管 v1 團隊** | `existing-team:v1` | dry-run 預覽，交易式升級並保留備份 | v2 manifest、執行期狀態、遷移日誌 |
| 🔍 **未知團隊** | `existing-team:audit` | 唯讀稽核，不自動覆寫 | 團隊遷移報告、風險與建議 |
| 🩺 **安裝品質檢查** | `doctor` | 唯讀校驗設定、角色、權限與符號連結 | `STATE=static_validation_done` 或明確失敗項 |
| 🧪 **Skill 自檢** | `skill-health` | 驗證 Skill 源碼包與深度回歸 | `STATE=skill_health_passed` |

> **不確定走哪條路？** 先執行 `python3 scripts/inspect_team.py --project <專案根目錄>`，不得僅憑專案名稱或目錄猜測。

---

## 快速開始

### 前置條件

- 支援 `SKILL.md` 的 AI 程式設計環境，例如 Codex、Claude Code、Cursor。
- Python 3.11+（使用標準庫 `tomllib` 解析設定）。
- Bash（用於 `install/` 下的安裝與 doctor 入口）。

### 作為 Skill 使用

```text
$multi-agent-team 初始化當前專案團隊
$multi-agent-team 稽核並最佳化當前團隊
$multi-agent-team 檢查團隊是否可用
```

### 直接呼叫指令

```bash
# 1. 先辨識目標專案狀態（唯讀）
python3 scripts/inspect_team.py --project <專案根目錄>

# 2. 新專案或既有業務專案：先預覽，不寫檔案
python3 scripts/team_init.py --project <專案根目錄> --profile auto

# 3. 使用者確認後才真正安裝；可用預設模型，也可按訂閱覆寫三檔模型 ID
python3 scripts/team_init.py --project <專案根目錄> --profile auto --thread-mode controlled-auto --apply \
  --model-fast <fast模型ID> --model-standard <standard模型ID> --model-advanced <advanced模型ID>

# 4. 受管 v1 團隊：先預覽，再交易式升級
python3 scripts/team_upgrade.py --project <專案根目錄> --thread-mode controlled-auto
python3 scripts/team_upgrade.py --project <專案根目錄> --thread-mode controlled-auto --apply \
  --model-fast <fast模型ID> --model-standard <standard模型ID> --model-advanced <advanced模型ID>

# 5. 未知或非受管團隊：唯讀稽核
python3 scripts/team_audit.py --project <專案根目錄>

# 6. 校驗安裝與執行期狀態
python3 scripts/team_doctor.py --project <專案根目錄>
python3 scripts/thread_orchestrator.py health --project <專案根目錄>
```

---

## 長期任務如何運作

1. 主任務把需求寫成任務 JSON，執行 `thread_orchestrator.py plan`。
2. 評分器回傳下表其中一個決策，並給出 Luna／Terra／Sol 模型檔位。
3. 只有 `controlled-auto` + `create_thread` 時，主任務才呼叫 Codex 客戶端任務工具；腳本不偽造任務 ID。
4. 客戶端回傳 ID 後用 `register --apply` 登記；階段性結果用 `update --summary ... --evidence ... --apply` 回傳。
5. 日常執行 `health`；若衍生狀態漂移，先 `reconcile` 預覽再 `--apply`。

| Planner 決策 | 主任務動作 |
|---|---|
| `handle_in_main` | 直接在主任務完成 |
| `use_subagents` | 於當前任務內使用邊界明確的一次性子智能體 |
| `recommend_thread` | 只推薦；需明確授權或改為 `controlled-auto` |
| `create_thread` | 主任務呼叫客戶端建立，成功後登記 ID |
| `reuse_thread` | 向 planner 回傳的 `existing_thread_id` 發送任務包 |
| `queue_or_reuse` | 已達活躍長期任務上限，先複用或收尾 |
| `queue_writer_capacity` | 已達並行寫入上限，排隊或縮小寫入邊界 |
| `blocked_ownership_conflict` | 解決路徑所有權衝突後再派發 |

> 任務 JSON 的完整欄位契約（欄位名、評分、必填與選填）見 `references/runtime-orchestration.md` 的「任務輸入欄位表」，可執行範例見 `examples/task-input.example.json`。欄位名以該表為準，不要用 `domain` 代替 `domain_key`、`est_days` 代替 `expected_days` 等別名。

---

## 角色與模型策略

### 角色檔案

| 檔案 | 角色 | 適用 |
|---|---|---|
| `core` | explorer、chore、implementer、debugger、architect、reviewer | 通用軟體專案 |
| `web` | core + e2e-tester | Web／UI、瀏覽器流程與截圖回歸 |
| `ai-data` | core + evidence-researcher | API、公開資料、證據鏈與供應商文件 |
| `full` | core + 兩類擴充角色 | 同時需要 Web 與資料證據時 |

### 模型與權限邊界

- explorer／chore：Luna 檔，低推理，探索唯讀或機械整理。
- implementer／debugger／e2e-tester／evidence-researcher：Terra 檔，常規實作、除錯與驗證。
- architect／reviewer：Sol 檔，高推理，架構決策與乾淨上下文獨立審查。
- explorer、architect、reviewer、evidence-researcher 為唯讀；其餘為 workspace-write。
- 執行中的實例不換腦；同因連續兩次失敗或風險升級時，保存現場後以更高檔位建立全新實例。

> `gpt-5.6-luna/terra/sol` 是目前 Codex 的預設三檔模型。不同訂閱可用範圍可能不同，必要時用 `--model-fast/--model-standard/--model-advanced` 覆寫；靜態 doctor 校驗一致性，實際可用性由全新 explorer/reviewer 冒煙確認。

既有 v2 團隊需要更換模型時，可用帶 `--model-*` 參數的 `team_upgrade.py` 先 dry-run、再 `--apply` 交易式更新；舊檔位無法安全判定時會拒絕猜測。

---

## 系統架構

![Multi-Agent Team 編排總覽](../assets/architecture/zh-CN/team-orchestration-overview.png)

- `SKILL.md` 只負責路由與硬約束，規則細節按需載入自 `references/`。
- 一切安裝／升級動作走 `scripts/`，預設 dry-run、marker 包裹、交易式寫入與備份回滾。
- 目標專案的執行期狀態全部外置在 `.codex/team/` 與 `docs/協作/`，主任務不依賴對話記憶。

### 既有專案的安全升級

![既有專案安全升級流程](../assets/architecture/zh-CN/safe-existing-skill-upgrade.png)

受管 v1 團隊經 `team_upgrade.py` 交易式升級到 v2；未知 schema fail-closed 並轉唯讀稽核，先備份再寫入，失敗即回滾。

---

## 指令參考

| 指令 | 說明 |
|---|---|
| `inspect_team.py --project <path>` | 唯讀辨識專案狀態與路由 |
| `team_init.py --project <path> [--profile] [--model-*] [--apply]` | 安裝協作層，預設 dry-run |
| `team_upgrade.py --project <path> [--apply]` | 受管 v1 → v2 交易式升級 |
| `team_audit.py --project <path>` | 未知團隊唯讀稽核並產生遷移報告 |
| `team_doctor.py --project <path>` | 目標專案安裝結果靜態校驗 |
| `thread_orchestrator.py plan/register/update/health/reconcile` | 長期任務規劃、登記、回傳、健康與對帳 |
| `health_check.py [--deep]` | Skill 源碼包自檢 |
| `regression_check.py` | 新／舊環境與執行期故障總回歸 |

---

## 開發與驗證

```bash
# 1. Skill 靜態健康檢查
python3 scripts/health_check.py --deep

# 2. 全量自檢：新環境與既有環境派生回歸
python3 scripts/regression_check.py

# 3. 防止測試依賴 Python assert 的最佳化模式複跑
PYTHONOPTIMIZE=1 python3 scripts/regression_check.py
```

三項全綠才算驗證通過。任何 `STATE=*_failed` 或 `partial_done` 均不得使用「完成」措辭。

---

## 🚦 專案狀態

- 目前狀態：`穩定可用`
- 版本階段：`1.0.1 · Stable`
- 相容範圍：`macOS / Linux · Python 3.11+ · Codex / Claude Code / Cursor`
- 已知風險與決策：見 [governance/RISKS.md](../governance/RISKS.md) 與 [governance/DECISIONS.md](../governance/DECISIONS.md)

---

## 常見問題

<details>
<summary><strong>需要每次都啟動 8 個角色嗎？</strong></summary>

不需要。模板數量不等於並行數量：即使安裝 8 個角色，同時最多執行 6 個實例，寫入實例最多 2 個。`auto` 檔案會依可驗證的建置檔與目錄訊號選擇最小角色集。
</details>

<details>
<summary><strong>既有專案會被重構或覆寫嗎？</strong></summary>

不會。安裝預設 dry-run，只追加受管協作層；既有 `AGENTS.md` 以穩定 marker 包裹追加，業務程式碼、設定與目錄結構一律不動，寫入前備份。
</details>

<details>
<summary><strong>為什麼 reviewer 不能複用實作執行緒？</strong></summary>

獨立審查必須基於乾淨上下文。reviewer 每次為全新唯讀實例，只接收驗收標準、最終 diff 與測試輸出，避免被實作過程的歷史結論影響判斷。
</details>

<details>
<summary><strong>模板裡的模型 ID 是真實的嗎？</strong></summary>

是目前 Codex 的預設模型 ID，但訂閱可用範圍可能不同。必要時用 `--model-fast/--model-standard/--model-advanced` 覆寫，並以全新 Agent 冒煙確認實際可用性。
</details>

---

## 參與貢獻

歡迎 Issue 與 PR。腳本修改須通過 `bash -n`／`py_compile` 與 `regression_check.py`；文件與制度修改請保持「按需載入、單一職責」。完整指南見 [CONTRIBUTING.md](../CONTRIBUTING.md)。

---

## 版本說明

| 版本 | 狀態 | 變更摘要 |
|---|---|---|
| `1.0.1` | 目前 | 三路由工作流、8 角色模板、三檔模型路由、長期任務評分、Token 與異常閘門、三類回歸 |

> 完整變更歷史見 [CHANGELOG.md](../CHANGELOG.md)，遵循 Keep a Changelog 與語意化版本。

---

## 致謝

[Codex CLI](https://github.com/openai/codex) · [Claude Code](https://github.com/anthropics/claude-code) · [Agent Skills 開放標準](https://agentskills.io)

---

## Star History

如果這個 Skill 對你有幫助，歡迎點亮一顆 Star ⭐

<a href="https://www.star-history.com/?type=date&repos=qierkang%2Fmulti-agent-team-skill">
  <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=qierkang/multi-agent-team-skill&type=date&legend=top-left" />
</a>

---

## 授權

本專案基於 [MIT License](../LICENSE) 開源。

---

## 作者

**qierkang**

- GitHub: <https://github.com/qierkang>
- Email: xyqierkang@gmail.com
