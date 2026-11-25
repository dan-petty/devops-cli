# Tasks

## 1. Extend PR plan builders and command options

Kind: behavior. Reads: `src/devops_cli/github/pr_plans.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_pr_dry_run.py`, `tests/commands/test_pr_cmd.py`. Changes: `src/devops_cli/github/pr_plans.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_pr_dry_run.py`, `tests/commands/test_pr_cmd.py`.

- [x] 1.1 Add failing tests in `tests/commands/test_pr_dry_run.py` and `tests/commands/test_pr_cmd.py` covering `pr view` (`--json`, `--jq`/`-q`, `--comments`/`-c`), `pr list` (`--json`, `--jq`/`-q`, `--search`/`-S`, `--head`/`-H`, `--base`/`-B`, raw-output failure without fallback), `pr status` (`--json`, `--jq`/`-q`, `--repo`/`-R`), `--dry-run` plans for all flags and `pr status`, and `devops gh pr view` / `list` / `status`
  - Verification: `$ uv run devops ci test tests/commands/test_pr_dry_run.py tests/commands/test_pr_cmd.py`
- [x] 1.2 Implement `pr_view_args`/`plan_pr_view`, `pr_list_args`/`plan_pr_list`, `pr_status_args`/`plan_pr_status` in `src/devops_cli/github/pr_plans.py`, wire options and `status_pr` in `src/devops_cli/commands/pr.py`, and add help strings in `src/devops_cli/lang/en/help.py`
  - Verification: `$ uv run devops ci test tests/commands/test_pr_dry_run.py tests/commands/test_pr_cmd.py`

## 2. Regenerate CLI documentation

Kind: other. Reads: `docs/commands/pr.md`, `docs/commands/gh.md`, `docs/CLI_REFERENCE.md`. Changes: `docs/commands/pr.md`, `docs/commands/gh.md`, `docs/CLI_REFERENCE.md`.

- [x] 2.1 Regenerate documentation with `uv run devops docs generate` and verify with `uv run devops docs check`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
