# Tasks

## 1. A scan that lacks a database is a coverage gap that names the command

Kind: behavior. Reads: `src/devops_cli/security/osv_scanner.py`, `src/devops_cli/security/trivy.py`, `src/devops_cli/security/golangci_lint.py` (the `coverage_gap` hook), `src/devops_cli/security/semgrep.py` (`_registry_rules_missing`). Changes: `src/devops_cli/security/osv_scanner.py`, `src/devops_cli/security/trivy.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/security/test_scanner_tool_executor.py`.

- [x] 1.1 Add six cases to `tests/security/test_scanner_tool_executor.py`: an osv-scanner run with the error `no offline version of the OSV database is available`, and a Trivy run with the error `failed to download vulnerability DB`, are coverage gaps with no finding and a reason that starts with the fetch command; an osv-scanner run on a database of 1 hour is `ran`; a run on a database of 25 hours is a coverage gap that keeps its finding; an old database of an ecosystem that the report does not name is `ran`; a tree with `rules.lock` and `uv.lock` names only `uv.lock`. Verify that `uv run devops ci test tests/security/test_scanner_tool_executor.py -k "fetch_command or old_database or old_osv or current_database or lock_file"` fails on the base (4 failed, 2 passed)
- [x] 1.2 Add `OsvScanner.coverage_gap`, the old-database gap of `OsvScanner.scan`, `lockfiles_of` and `report_ecosystems`, and `TrivyScanner.coverage_gap`. A lockfile is a file whose name is in `CONST_LOCKFILE_NAMES`, with no rule for the suffix `.lock`. Verify that `uv run devops ci test tests/security/test_scanner_tool_executor.py tests/security/test_osv_scanner.py tests/security/test_review_tool_runs.py` passes

## 2. One command fetches the databases

Kind: behavior. Reads: `src/devops_cli/commands/review.py` (`rules_fetch`), `src/devops_cli/core/process.py` (`run_subprocess`), `tests/support/fakes/process.py`. Changes: `src/devops_cli/security/tool_databases.py`, `src/devops_cli/commands/review.py`, `src/devops_cli/config/commands.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/help.py`, `tests/security/test_tool_databases.py`, `tests/commands/test_review_fetch_databases.py`, `tests/ai/mcp/test_mcp.py`.

- [x] 2.1 Add `tests/security/test_tool_databases.py` for the plan and the fetch, over `process_fake`, and `tests/commands/test_review_fetch_databases.py` for the command and its dry run. List the command in the commands that the MCP server does not expose (`tests/ai/mcp/test_mcp.py`): it writes the user cache and it takes minutes. Verify that `uv run devops ci test tests/security/test_tool_databases.py tests/commands/test_review_fetch_databases.py` fails on the base because the module and the command do not exist
- [x] 2.2 Add `devops review fetch-databases [PATH]` and `src/devops_cli/security/tool_databases.py`. Verify that `uv run devops ci test tests/security/test_tool_databases.py tests/commands/test_review_fetch_databases.py tests/ai/mcp/test_mcp.py` passes

## 3. Documents

Kind: other. Changes: `docs/SELF_IMPROVEMENT.md`, `SECURITY.md`, `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/review.md`, `docs/commands/ai.md`.

- [x] 3.1 Say the fetch step in `docs/SELF_IMPROVEMENT.md` and `SECURITY.md`, then regenerate the command documents with `uv run devops docs generate --sync-readme`. Verify that `uv run devops ci docs` passes
