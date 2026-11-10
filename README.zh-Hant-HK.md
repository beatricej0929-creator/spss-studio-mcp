# SPSS Studio MCP for Mac

> 令 SPSS 成為 Agent 的「統計引擎 + 製圖工廠」：達到投稿水準的圖片、深度結果剖析、方法真機驗證、安全執行。

> 此 MCP **僅為 Mac** 提供支援，需要 Windows 版本之 MCP
> 請參閲 [flupke91/spss-studio-mcp](https://github.com/flupke91/spss-studio-mcp)。

[English](README.md) ｜ **繁體中文（香港）**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.14%2B-blue.svg)]()
[![Tests](https://img.shields.io/badge/tests-113%20passed-brightgreen.svg)]()

`spss-studio-mcp` 是一個面向 **IBM SPSS Statistics** 的 MCP（Model Context Protocol）伺服器，為 Codex / Claude Code /
Cursor 等 Agent 用戶端提供：

- **達到投稿水準的圖表**：11 類 `spss_chart_*` 工具，一鍵匯出 PNG / TIFF （1950×1500 @300 dpi），回傳檔案路徑可直接投稿；
- **深度結果剖析**：OMS 文字 → Markdown 表格 + 結構化 JSON + 16 類分析統計摘要 （t / F / r / B / Wald / α / χ² / p / 效應量）；
- **方法真機驗證**：全部 37 個分析工具加 11 個輔助工具均在真實 SPSS 32 for Mac 上驗證；
- **中介 / 調節**：`spss_process` 會呼叫本機 Hayes PROCESS，支援模型 4
  的單一／並行中介 Bootstrap；另保留 `spss_mediation` 三步迴歸 + Sobel
  檢驗與 `spss_moderation` 中心化交互迴歸；
- **安全執行層**：危險指令攔截、資料路徑白名單、`dry_run` 預檢、JSONL 審計日誌。

目前測試套件為 **113 項通過、1 項跳過**，並包含自包含真機重現清單；既有分析能力已在 **IBM SPSS Statistics 32.0.0.0（macOS）** 驗證。逐條結果見
[docs/macos_verification.zh-Hant-HK.md](docs/macos_verification.zh-Hant-HK.md)。

---

## 安裝

**環境要求**：macOS · Python 3.10+ · IBM SPSS Statistics for Mac。 已在 SPSS 32.0.0.0 驗證，會自動偵測 `/Applications` 下的
SPSS；若未安裝 SPSS，則只有讀取檔案的工具有效。

```bash
git clone https://github.com/beatricej0929-creator/spss-studio-mcp.git
cd spss-studio-mcp
bash scripts/install_macos.sh          # .venv + 依賴 + 狀態檢查 + Claude Code 設定
bash scripts/install_macos.sh --codex  # 同上，但改寫 Codex 設定
bash scripts/install_macos.sh --local  # Claude Code → ~/.claude/settings.local.json
```

安裝腳本會建立 `.venv`、安裝 `-e ".[dev]"`、執行狀態檢查，並寫入 MCP 用戶端設定。

### 1. 驗證

```bash
.venv/bin/spss-studio-mcp status
# pyreadstat : OK v1.3.6
# pandas     : OK v3.0.5
# SPSS batch : OK - /Applications/IBM SPSS Statistics/IBM SPSS Statistics.app/Contents/bin/spssengine
```

若顯示 `SPSS batch : NOT FOUND`，表示自動偵測失敗，請設定
`SPSS_INSTALL_PATH`（見下方及
[docs/macos_verification.zh-Hant-HK.md](docs/macos_verification.zh-Hant-HK.md)）。

### 2. 設定用戶端

| 用戶端          | 指令                                         | 寫入位置                                      |
|-----------------|----------------------------------------------|-----------------------------------------------|
| Claude Code     | `.venv/bin/spss-studio-mcp configure-claude` | `~/.claude.json` → `mcpServers.spss`          |
| Codex           | `.venv/bin/spss-studio-mcp configure-codex`  | `~/.codex/config.toml` → `[mcp_servers.spss]` |
| 其他 MCP 用戶端 | `.venv/bin/spss-studio-mcp setup-info`       | 印出 JSON 片段，自行貼上                      |

兩個指令都是合併寫入既有檔案，並留下帶時間戳的備份 （`*.backup.YYYYMMDD_HHMMSS`）；`configure-claude --local` 改寫
`~/.claude/settings.local.json`。 **請重新啟動用戶端**，然後叫它執行
`spss_check_status` 確認伺服器已連上。

### 手動 MCP 設定

安裝腳本會把 `spss-studio-mcp` 連到 `~/.local/bin`，因此任何用戶端都能直接以
指令名稱解析。複製以下對應片段即可，毋須修改路徑。

> 若你使用了 `--no-link`，或 `~/.local/bin` 不在你的 `PATH` 上，請改寫成
> clone 目錄的絕對路徑
> （`/absolute/path/to/spss-studio-mcp/.venv/bin/spss-studio-mcp`）。

**Claude Code** —— `~/.claude.json`，或專案根目錄的 `.mcp.json`：

```json
{
  "mcpServers": {
    "spss": {
      "type": "stdio",
      "command": "spss-studio-mcp",
      "args": ["serve", "--transport", "stdio"]
    }
  }
}
```

**Codex** —— `~/.codex/config.toml`（此檔為 **TOML**，並非 JSON）：

```toml
[mcp_servers.spss]
command = "spss-studio-mcp"
args = ["serve", "--transport", "stdio"]
```

Codex 預設會在 60 秒後中止工具呼叫；若分析需時更久，可在該表格內加上
`tool_timeout_sec = 600`。

**Gemini CLI** —— `~/.gemini/settings.json`，或專案根目錄的
`.gemini/settings.json`：

```json
{
  "mcpServers": {
    "spss": {
      "command": "spss-studio-mcp",
      "args": ["serve", "--transport", "stdio"]
    }
  }
}
```

Gemini CLI 的預設請求逾時為 10 分鐘，已足夠完成一次完整分析，毋須設定
`timeout`。

若 `status` 顯示 `SPSS batch : NOT FOUND`，請在該項目中加入 `env` 指定偵測
路徑：

```json
"env": {
  "SPSS_INSTALL_PATH": "/Applications/IBM SPSS Statistics/IBM SPSS Statistics.app/Contents/bin"
}
```

修改後請**重新啟動用戶端**，MCP 設定只會在啟動時讀取一次。

### 手動安裝

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"   # 只要執行環境可用 -e .
.venv/bin/spss-studio-mcp configure-claude    # 或 configure-codex / setup-info
```

### 環境變數

| 變數                   | 預設值             | 用途                                                                       |
|------------------------|--------------------|----------------------------------------------------------------------------|
| `SPSS_INSTALL_PATH`    | 自動偵測           | SPSS `.app`、`Contents/bin` 或 `spssengine` 執行檔；僅在偵測失敗時才需設定 |
| `SPSS_TIMEOUT`         | `120`              | 單次分析逾時（秒）                                                         |
| `SPSS_STARTUP_TIMEOUT` | `300`              | 引擎啟動逾時；授權與 Python 初始化較慢                                     |
| `SPSS_NO_SPSS`         | `0`                | 設為 `1` 強制使用純檔案模式                                                |
| `SPSS_ALLOWED_DIRS`    | —                  | 以 `;` 分隔的額外可用資料目錄                                              |
| `SPSS_AUDIT_LOG`       | `logs/audit.jsonl` | 審計日誌路徑                                                               |
| `SPSS_PROCESS_MACRO_PATH` | 自動偵測       | 專用 `spss_process` 工具所使用的可信本機 `process.sps` 路徑                 |

### Hayes PROCESS 中介分析

`spss_process` 在不開放通用 `INSERT FILE` 的前提下，安全載入已設定的本機
PROCESS 巨集。首版支援模型 4：單一或多個並行中介、Bootstrap 信賴區間、
控制變項、間接效應成對比較、效應量與標準化係數。

本儲存庫**不附帶 PROCESS 本體**。請從
[Andrew F. Hayes 官方網站](https://www.afhayes.com/download.html)下載，把其中的
`process.sps` 保存在本機，然後讓本 MCP 從 SPSS 安裝位置旁自動偵測，或設定
`SPSS_PROCESS_MACRO_PATH`。不需要安裝可選的 SPSS 圖形選單。PROCESS 是第三方
軟件，仍受其自身的版權與使用條款約束。

```python
spss_process(
    file_path="examples/data/mediation_study.sav",
    x="autonomy",
    y="performance",
    mediators=["satisfaction"],
    bootstrap_samples=5000,
    confidence=95,
    seed=2026,
)
```

完整教學見 [docs/tutorial.zh-Hant-HK.md](docs/tutorial.zh-Hant-HK.md)。

## 達到投稿水準的圖表（核心賣點）

| 工具                                                    | 用途                                |
|---------------------------------------------------------|-------------------------------------|
| `spss_chart_histogram` / `spss_chart_histogram_density` | 分佈直方圖 / 直方圖 + 常態密度      |
| `spss_chart_scatter`                                    | 兩變項散點圖                        |
| `spss_chart_bar` / `spss_chart_bar_error`               | 分類平均值長條圖 / 連 95% CI 誤差鬚 |
| `spss_chart_line` / `spss_chart_area`                   | 時間序列折線 / 面積圖               |
| `spss_chart_boxplot`                                    | 分組箱線圖                          |
| `spss_chart_errorbar`                                   | 平均值 ± CI 誤差條                  |
| `spss_chart_qqplot`                                     | 常態 Q-Q 圖                         |
| `spss_chart_km_curve`                                   | Kaplan-Meier 存活曲線               |

```python
spss_chart_histogram_density(
    variable="engagement_total",
    title="學習投入總分分佈（帶常態密度）",
    image_format="PNG",  # PNG / TIFF
    width_px=1950, height_px=1500, dpi=300,
    data_file="examples/data/survey_study.sav",
)
# → 回傳圖片檔案路徑，可直接投稿
```

> **macOS 注意**：本專案僅支援 macOS 上的 SPSS，圖表輸出格式為 PNG 與 TIFF。
> SPSS for Mac 只會產生點陣輸出，不會產生 Windows 向量 EMF（其 `OMS FORMAT=DOC`
> 封存內是 PNG 資料），因此 EMF 匯出已從產品中移除；請使用
> `image_format="PNG"` 或 `"TIFF"`。

## 結構化結果與統計摘要

```python
spss_structured_result(
    syntax="T-TEST GROUPS=group(1 2) /VARIABLES=posttest.",
    data_file="examples/data/experiment_study.sav",
)
# → {markdown, json: {tables, summary}, files, warnings}
```

`run_syntax` 回傳的 Markdown 末尾會附上一個 `### Statistical Summary` 區塊， 內含平白語言結論加上關鍵統計量。 16
類分析的抽取細節見：[docs/result_parsing.zh-Hant-HK.md](docs/result_parsing.zh-Hant-HK.md)。

## 範例資料

`examples/data/` 提供五組貼近論文場景的範例資料（固定隨機種子，可完整重現）：

| 檔案                                        | 場景                       | 關鍵變項                                             |
|---------------------------------------------|----------------------------|------------------------------------------------------|
| `survey_study.sav`                          | 問卷：200 位學生學習投入   | `gender` / `major` / `q1`–`q12` / `engagement_total` |
| `experiment_study.sav`                      | 實驗：120 人記憶訓練前後測 | `group` / `pretest` / `posttest` / `gain`            |
| `survival_study.sav`                        | 存活：150 例隨訪           | `treatment` / `time` / `status`                      |
| `mediation_study.sav`                       | 中介：300 名僱員           | `autonomy` / `satisfaction` / `performance`          |
| `longitudinal_study.sav` / `long_study.sav` | 縱向：60 人 3 次測量       | `id` / `group` / `time` / `score`                    |

## 安全執行

- 危險指令（`HOST` / `ERASE` / `DELETE FILE` 等）在行首即被攔截；
- 資料檔案必須位於 `examples/`、系統暫存目錄，或 `SPSS_ALLOWED_DIRS` 所宣告的目錄；
- `spss_run_syntax(..., dry_run=True)` 先校驗、不執行；
- 審計日誌預設寫入 `logs/audit.jsonl`（可用 `SPSS_AUDIT_LOG` 更改路徑）。

詳見 [docs/security.zh-Hant-HK.md](docs/security.zh-Hant-HK.md)。

## 文件

- [教學](docs/tutorial.zh-Hant-HK.md)
- [技術報告](docs/technical_report.zh-Hant-HK.md)
- [圖表管線 PoC 與 SPSS 32 發現](docs/poc_chart_pipeline.zh-Hant-HK.md)
- [結果剖析（16 類分析摘要）](docs/result_parsing.zh-Hant-HK.md)
- [方法真機驗證](docs/method_verification.zh-Hant-HK.md)
- [macOS 真機驗證報告（SPSS 32 for Mac）](docs/macos_verification.zh-Hant-HK.md)
- [安全層](docs/security.zh-Hant-HK.md)

## 許可證

MIT（上游：`flupke91/spss-studio-mcp`，MIT）。

MIT（上游：`Exekiel179/SPSS-MCP`，MIT）。
