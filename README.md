# SPSS Studio MCP for Mac

> Make SPSS an Agent's "statistics engine + chart factory": paper-ready charts, deep result parsing, verified methods, and safe execution.

> This MCP is **Mac Only**, for Windows versions, see [flupke91/spss-studio-mcp](https://github.com/flupke91/spss-studio-mcp).

**English** ｜ [繁體中文（香港）](README.zh-Hant-HK.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.14%2B-blue.svg)]()
[![Tests](https://img.shields.io/badge/tests-113%20passed-brightgreen.svg)]()

`spss-studio-mcp` is an MCP (Model Context Protocol) server for **IBM SPSS
Statistics**. It gives Agent clients such as Codex / Claude Code / Cursor:

- **Paper-ready charts**: 11 `spss_chart_*` tools export PNG / TIFF
  (1950×1500 @300 dpi) in one call and return the file path for direct
  submission to journals;
- **Deep result parsing**: OMS text → Markdown tables + structured JSON +
  statistical summaries for 16 analysis families (t / F / r / B / Wald / α /
  χ² / p / effect sizes);
- **Verified methods**: all 37 analysis tools plus 11 supporting tools are
  verified on real SPSS Statistics 32 for Mac;
- **Mediation / moderation**: `spss_process` runs the locally installed Hayes
  PROCESS macro for model 4 bootstrap mediation (single or parallel mediators),
  alongside the legacy `spss_mediation` three-step/Sobel workflow and
  `spss_moderation` mean-centred interaction regression;
- **Safety layer**: dangerous-command blocking, data path allowlist,
  `dry_run` preflight, and JSONL audit logging.

The test suite currently reports **113 passed and 1 skipped**, including a
self-contained real-machine reproduction manifest. Existing analysis families
were verified on **IBM SPSS Statistics 32.0.0.0 for macOS**.
Per-case results: [docs/macos_verification.md](docs/macos_verification.md).

---

## Installation

**Requirements**: macOS · Python 3.10+ · IBM SPSS Statistics for Mac.
SPSS 32.0.0.0 is verified and auto-detected under `/Applications`; without it
only the file-reading tools work.

```bash
git clone https://github.com/beatricej0929-creator/spss-studio-mcp.git
cd spss-studio-mcp
bash scripts/install_macos.sh          # .venv + deps + status + Claude Code config
bash scripts/install_macos.sh --codex  # same, but writes the Codex config
bash scripts/install_macos.sh --local  # Claude Code → ~/.claude/settings.local.json
```

The installer creates `.venv`, installs `-e ".[dev]"`, runs a status check, and
writes the MCP client config.

### 1. Verify

```bash
.venv/bin/spss-studio-mcp status
# pyreadstat : OK v1.3.6
# pandas     : OK v3.0.5
# SPSS batch : OK - /Applications/IBM SPSS Statistics/IBM SPSS Statistics.app/Contents/bin/spssengine
```

`SPSS batch : NOT FOUND` means auto-detection failed — set `SPSS_INSTALL_PATH`
(see below and [docs/macos_verification.md](docs/macos_verification.md)).

### 2. Configure your client

| Client          | Command                                              | Written to                                    |
| --------------- | ---------------------------------------------------- | --------------------------------------------- |
| Claude Code     | `.venv/bin/spss-studio-mcp configure-claude`         | `~/.claude.json` → `mcpServers.spss`          |
| Codex           | `.venv/bin/spss-studio-mcp configure-codex`          | `~/.codex/config.toml` → `[mcp_servers.spss]` |
| Other MCP hosts | `.venv/bin/spss-studio-mcp setup-info`               | prints a JSON snippet to paste manually       |

Both commands merge into the existing file and leave a timestamped backup
(`*.backup.YYYYMMDD_HHMMSS`). `configure-claude --local` targets
`~/.claude/settings.local.json` instead. **Restart the client**, then ask it to
run `spss_check_status` to confirm the server is connected.

### Manual MCP configuration

The installer symlinks `spss-studio-mcp` into `~/.local/bin`, so the plain
command name resolves in any client. Copy the matching snippet below — no path
editing needed.

> If you passed `--no-link`, or `~/.local/bin` is not on your `PATH`, substitute
> the absolute path to your clone
> (`/absolute/path/to/spss-studio-mcp/.venv/bin/spss-studio-mcp`).

**Claude Code** — `~/.claude.json`, or `.mcp.json` at a project root:

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

**Codex** — `~/.codex/config.toml`. This file is **TOML**, not JSON:

```toml
[mcp_servers.spss]
command = "spss-studio-mcp"
args = ["serve", "--transport", "stdio"]
```

Codex aborts a tool call after 60 s by default. Add `tool_timeout_sec = 600`
inside the table if an analysis needs longer.

**Gemini CLI** — `~/.gemini/settings.json`, or `.gemini/settings.json` at a
project root:

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

Gemini CLI's default request timeout is 10 minutes, which already covers a full
analysis run, so no `timeout` key is needed.

If `status` reports `SPSS batch : NOT FOUND`, add the detection path to the
entry's `env`:

```json
"env": {
  "SPSS_INSTALL_PATH": "/Applications/IBM SPSS Statistics/IBM SPSS Statistics.app/Contents/bin"
}
```

Restart the client after editing — MCP configuration is read at startup only.

### Manual install

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"   # -e . for runtime only
.venv/bin/spss-studio-mcp configure-claude    # or configure-codex / setup-info
```

### Environment variables

| Variable               | Default            | Purpose                                                                                      |
| ---------------------- | ------------------ | -------------------------------------------------------------------------------------------- |
| `SPSS_INSTALL_PATH`    | auto-detected      | SPSS `.app` bundle, `Contents/bin`, or the `spssengine` binary — set only if detection fails |
| `SPSS_TIMEOUT`         | `120`              | Per-analysis timeout, seconds                                                                |
| `SPSS_STARTUP_TIMEOUT` | `300`              | Engine startup timeout; licensing and Python init can be slow                                |
| `SPSS_NO_SPSS`         | `0`                | Set to `1` to force file-only mode                                                           |
| `SPSS_ALLOWED_DIRS`    | —                  | `;`-separated extra directories allowed as data sources                                      |
| `SPSS_AUDIT_LOG`       | `logs/audit.jsonl` | Audit log path                                                                               |
| `SPSS_PROCESS_MACRO_PATH` | auto-detected   | Trusted local `process.sps` used only by the dedicated `spss_process` tool                  |

### Hayes PROCESS mediation

`spss_process` safely loads the configured local PROCESS macro without exposing
the blocked general-purpose `INSERT FILE` command. The first release supports
PROCESS model 4: one mediator or multiple parallel mediators, bootstrap
confidence intervals, optional covariates, pairwise indirect-effect contrasts,
effect sizes, and standardized coefficients.

PROCESS itself is **not bundled with this repository**. Download it from the
[official Andrew F. Hayes website](https://www.afhayes.com/download.html), keep
the supplied `process.sps` on the local machine, and either let this MCP detect
it beside the SPSS installation or set `SPSS_PROCESS_MACRO_PATH`. Installing the
optional SPSS graphical dialog is not required. PROCESS is third-party software
and remains subject to its own copyright and usage terms.

```python
spss_process(
    file_path="examples/data/mediation_study.sav",
    x="autonomy",
    y="performance",
    mediators=["satisfaction"],
    model=4,
    bootstrap_samples=5000,
    confidence=95,
    seed=2026,
)
```

The macro is auto-detected next to an installed SPSS distribution. If it is
stored elsewhere, set `SPSS_PROCESS_MACRO_PATH=/absolute/path/process.sps` and
restart the MCP client.

Full walkthrough: [docs/tutorial.md](docs/tutorial.md).

## Paper-Ready Charts (Core Feature)

| Tool                                                    | Purpose                                              |
| ------------------------------------------------------- | ---------------------------------------------------- |
| `spss_chart_histogram` / `spss_chart_histogram_density` | Histogram / histogram with normal density            |
| `spss_chart_scatter`                                    | Scatter plot of two variables                        |
| `spss_chart_bar` / `spss_chart_bar_error`               | Bar chart of category means / with 95% CI error bars |
| `spss_chart_line` / `spss_chart_area`                   | Time-series line / area charts                       |
| `spss_chart_boxplot`                                    | Grouped box-and-whisker plot                         |
| `spss_chart_errorbar`                                   | Mean ± CI error bar chart                            |
| `spss_chart_qqplot`                                     | Normal Q-Q plot                                      |
| `spss_chart_km_curve`                                   | Kaplan-Meier survival curve                          |

```python
spss_chart_histogram_density(
    variable="engagement_total",
    title="Engagement total distribution (with normal density)",
    image_format="PNG",            # PNG / TIFF
    width_px=1950, height_px=1500, dpi=300,
    data_file="examples/data/survey_study.sav",
)
# → returns the image file path, ready for submission
```

> **Format note**: chart output is **PNG and TIFF only**. Windows vector EMF
> export was removed because SPSS for macOS cannot produce EMF metafiles (its
> `OMS FORMAT=DOC` archive contains only raster PNG wrapped in `.eps`). Use
> `image_format="PNG"` or `"TIFF"`.

## Structured Results & Statistical Summaries

```python
spss_structured_result(
    syntax="T-TEST GROUPS=group(1 2) /VARIABLES=posttest.",
    data_file="examples/data/experiment_study.sav",
)
# → {markdown, json: {tables, summary}, files, warnings}
```

The Markdown returned by `run_syntax` ends with a `### Statistical Summary`
block containing a plain-language conclusion plus key statistics.
Extraction details for the 16 analysis families: [docs/result_parsing.md](docs/result_parsing.md).

## Sample Datasets

`examples/data/` ships five research-style datasets (fixed random seeds,
fully reproducible):

| File                                        | Scenario                                               | Key variables                                        |
| ------------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------- |
| `survey_study.sav`                          | Survey: 200 students' learning engagement              | `gender` / `major` / `q1`–`q12` / `engagement_total` |
| `experiment_study.sav`                      | Experiment: 120 participants, pre/post memory training | `group` / `pretest` / `posttest` / `gain`            |
| `survival_study.sav`                        | Survival: 150 follow-up cases                          | `treatment` / `time` / `status`                      |
| `mediation_study.sav`                       | Mediation: 300 employees                               | `autonomy` / `satisfaction` / `performance`          |
| `longitudinal_study.sav` / `long_study.sav` | Longitudinal: 60 people, 3 waves                       | `id` / `group` / `time` / `score`                    |

## Safe Execution

- Dangerous commands (`HOST` / `ERASE` / `DELETE FILE`, ...) are blocked at
  the start of a line;
- Data files must live under `examples/`, the system temp dir, or a directory
  declared in `SPSS_ALLOWED_DIRS`;
- `spss_run_syntax(..., dry_run=True)` validates without executing;
- Audit logs are written to `logs/audit.jsonl` by default
  (override with `SPSS_AUDIT_LOG`).

See [docs/security.md](docs/security.md).

## Documentation

- [Tutorial](docs/tutorial.md)
- [Technical report](docs/technical_report.md)
- [Chart pipeline PoC & SPSS 32 findings](docs/poc_chart_pipeline.md)
- [Result parsing (16 analysis families)](docs/result_parsing.md)
- [Method verification](docs/method_verification.md)
- [macOS verification report (SPSS 32 for Mac)](docs/macos_verification.md)
- [Security layer](docs/security.md)

## License

MIT (upstream: `flupke91/spss-studio-mcp`, MIT).

MIT (upstream: `Exekiel179/SPSS-MCP`, MIT).
