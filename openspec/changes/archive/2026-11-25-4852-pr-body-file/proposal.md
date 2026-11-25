# Proposal: #4852

## Why

`devops pr create` and `devops pr edit` currently take pull request descriptions only through inline `--body` strings, which break shell quoting on Markdown backticks and quotes (#4852). Agents invoked `gh`'s `--body-file` option 33 times against these commands and failed with unknown-option errors. (Other `pr` pass-through work from the earlier discussion was split to #5908.)

## What Changes

- Add `--body-file` / `-F` (`typer.FileText | None = None`) to both `devops pr create` and `devops pr edit`, reading UTF-8 text from a file or `-` for standard input.
- Introduce one shared body-resolution helper (`_resolve_body_input`) in `src/devops_cli/commands/pr.py` that reads the file once, forwards `--body <text>` to `gh`, and exits `2` with a bad-parameter error naming both `--body` and `--body-file` when both options are given.
- Apply `pr create`'s 1,000-character limit and template-text refusal (`_form_checked`) to text read from `--body-file`.
- Register `pr_edit`'s `body_file` parameter in `PATH_CONFINEMENTS` (`src/devops_cli/ai/mcp/path_confinement.py`), update the MCP tool listing snapshot, and regenerate `docs/commands/pr.md`, `docs/CLI_REFERENCE.md`, and `docs/MCP_TOOLS.md`.

## Capabilities

### Modified Capabilities
- `pull-request-form`: Support `--body-file` / `-F` (and `-` stdin) with `--body` mutual exclusion and form validation on `pr create` and `pr edit`.

## Impact

- Single pull request scoped to `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/ai/mcp/path_confinement.py`, regenerated command/MCP docs, MCP tool listing snapshot, and PR command tests.

## Feasibility

Confirmed against the current codebase (`origin/main`):
- `rg -n "body-file|body_file" src/devops_cli/commands/pr.py` returns no matches.
- `create_pr` and `edit_pr` in `src/devops_cli/commands/pr.py` only declare `--body` / `-b`.
- `gh issue close --comment-file` (`src/devops_cli/commands/gh.py:1398-1415`) already uses `typer.FileText` to read UTF-8 files and `-` for standard input.

## Existing Tool Considered

Click (`pallets/click`, already in use through Typer) provides `typer.FileText` for file reading, `-` stdin handling, and exit-2 missing-file parameter errors (`src/devops_cli/commands/gh.py:1413`). We reuse Click's `FileText` directly and build only the thin shared option helper and mutual-exclusion check (~8k tokens to build, ~2k tokens/year to keep), deleting no code.
