# Security Layer (P4)

> **Language:** [English](security.md) · [繁體中文（香港）](security.zh-Hant-HK.md)

> Implementation date: 2026-08-05 | Real-machine verification: SPSS 32.0.0 (dry_run / dangerous-command blocking / audit all passed)

## Modules

`src/spss_mcp/security.py`

| Capability | Implementation |
|------|------|
| Dangerous-command blocking | `check_syntax_safety(syntax)`: matches `HOST / ERASE / DELETE FILE / FILE HANDLE / INSERT FILE / SCRIPT / CD / SYSTEM` at the start of a line, avoiding false positives from variable names |
| Path allowlist | `validate_data_file(path)`: allows `SPSS_ALLOWED_DIRS` (semicolon-separated), the project's `examples/`, and the system temporary directory; rejects paths that do not exist or are outside the allowlist |
| Audit logging | `audit(entry)`: appends JSONL to `logs/audit.jsonl` (path can be changed with `SPSS_AUDIT_LOG`); a failure never blocks analysis |
| dry_run | `spss_run_syntax(..., dry_run=True)`: only validates syntax safety and paths; does not start execution |

## Integration Points

- `spss_runner.run_syntax`: the unified security gate (shared by all tools) — it first blocks dangerous commands, then validates the `data_file` parameter and the `GET FILE='...'` paths in the syntax; every successful execution writes an audit entry.
- `server.spss_run_syntax`: adds the `dry_run` parameter; `spss_structured_result` also passes through the `run_syntax` security gate.
- `server.spss_process`: reads only the auto-detected or
  `SPSS_PROCESS_MACRO_PATH`-configured local `process.sps`; the macro path is not
  accepted from tool callers. This enables Hayes PROCESS without permitting
  arbitrary `INSERT FILE` execution.

## Audit Events

| event | Meaning |
|-------|------|
| `blocked / dangerous_syntax` | The syntax contains dangerous commands; not executed |
| `blocked / path` | The data file does not exist or is not on the allowlist; not executed |
| `dry_run` | A dry_run validation request (includes the list of blocked commands) |
| `syntax_run` | Normal execution (includes a summary of the first syntax line, data_file, success, error) |

## Real-Machine Verification Log

```
dry_run:          Dry run: syntax is safe to execute ...
HOST syntax:      Error: Syntax blocked: dangerous commands HOST.
Normal analysis:  Passed (FREQUENCIES returns normally)
External path:    Error: Data file does not exist: /Users/me/outside/x.sav
Audit log:        dry_run / blocked / syntax_run events all written to disk
```

## Configuration

```bash
export SPSS_ALLOWED_DIRS="/Users/me/Research/data;/Users/me/MoreData"  # additional allowed data directories (semicolon-separated)
export SPSS_AUDIT_LOG="/Users/me/logs/spss-audit.jsonl"                # audit log location
```
