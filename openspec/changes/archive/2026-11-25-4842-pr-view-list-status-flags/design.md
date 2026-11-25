# Design

## Decisions

- **Extend `pr_view_args`/`plan_pr_view` and `pr_list_args`/`plan_pr_list` and add `pr_status_args`/`plan_pr_status` in `src/devops_cli/github/pr_plans.py`.**: Both execution and `--dry-run` request plans share one argument builder per verb (`src/devops_cli/github/pr_plans.py:23-85`), preventing plan-vs-runtime drift (`tests/commands/test_pr_dry_run.py:176`).
- **Use caller-supplied `--json` in `pr_list_args` instead of the fixed table field list when provided.**: `gh pr list` takes one `--json` flag (`src/devops_cli/github/pr_plans.py:37`); keeping default table fields only when `--json` is omitted preserves existing table output for `devops pr list --search ... --base ...` while producing requested fields when `--json` is given.
- **Branch to raw stdout and non-fallback error handling when `--json` or `--jq` is passed.**: `list_prs` and `view_pr` currently render tables and invoke REST fallbacks (`src/devops_cli/commands/pr.py:259-272, 423-430`); emitting masked stdout directly on success and masked `gh` error without fallback on failure preserves the requested JSON/jq output contract.
- **Keep option short flags `-q` (`--jq`), `-c` (`--comments`), `-S` (`--search`), `-H` (`--head`), `-B` (`--base`) matching `gh`.**: Avoids colliding with existing `-s` (`--state`), `-n` (`--limit`), and `-R` (`--repo`) in `src/devops_cli/commands/pr.py:234-245`.

## Rejected alternatives

- **Add a separate wrapper in `src/devops_cli/commands/gh.py`.**: `src/devops_cli/commands/gh.py:143` already mounts `pr_app` directly at `devops gh pr`; duplicating handlers in `gh.py` would drift.
- **Validate `--json` field names locally.**: `gh` already validates PR JSON fields and reports invalid field errors directly (`src/devops_cli/commands/pr.py:423`); a local allowlist would go stale on `gh` updates.
- **Modify `devops pr checks` and `devops pr diff` in this change.**: Issue `#4842` targets only `pr view`, `pr list`, and `pr status`; `pr checks` already powers readiness tables and `pr diff` passes `--color`.
