# Design

## Decisions

1. **Use `typer.FileText` in a shared `_resolve_body_input` helper.**
   `gh issue close --comment-file` already uses `typer.FileText` (`src/devops_cli/commands/gh.py:1398-1415`), which reads UTF-8 files, handles `-` for standard input, and exits `2` with Click's standard missing-file error before entering the command body. The shared helper refuses `body is not None and body_file is not None` using `typer.BadParameter`, naming both `--body` and `--body-file`.

2. **Forward resolved text as `--body` to `gh` in both live and dry-run modes.**
   Once `_resolve_body_input` reads `body_file` cleanly once, `plan_pr_create`, `_form_checked`, `pr_create_args`, `plan_pr_edit`, and `pr_edit_args` operate on the resolved text string without re-reading stdin or exposing raw file paths to `gh` (`src/devops_cli/github/pr_plans.py:102-177`).

3. **Declare `pr_edit`'s `body_file` in `PATH_CONFINEMENTS`.**
   `pr edit` is published on MCP via `CONST_MCP_EXPOSURE_TABLE` (`tests/ai/mcp/test_mcp_tool_registry.py:199`). Adding `"pr_edit": frozenset({"body_file"})` in `src/devops_cli/ai/mcp/path_confinement.py` satisfies `tests/ai/mcp/test_path_confinement.py` without custom exemption code.

## Rejected alternatives

- **Reuse `devops roadmap intake --body-file` (`Path(exists=True)`).** Rejected: `Path.read_text` rejects `-`, which is required for standard input (`src/devops_cli/commands/roadmap.py:144-171`).
- **Pass `--body-file` through directly to `gh`.** Rejected: `_form_checked` validates the PR body before `gh` runs (`src/devops_cli/commands/pr.py:1212-1266`), and reading `-` once would consume standard input before `gh` could read it.
- **Add custom `open()` logic instead of `typer.FileText`.** Rejected: duplicates Click's file-open, stdin `-`, and parameter error reporting.
