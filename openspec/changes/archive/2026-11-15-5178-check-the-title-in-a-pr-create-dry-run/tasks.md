# Tasks

## 1. Check the scope in the dry run

Reads: `src/devops_cli/commands/pr.py`, `src/devops_cli/github/labels.py`.

Changes: `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/pull_form.py`, `tests/commands/test_pr_dry_run.py`.

- [x] 1.1 Write the two dry-run tests, and watch them fail.
  - Verification: `$ uv run devops ci test tests/commands/test_pr_dry_run.py`
- [x] 1.2 Read the checkout labels in the dry run, and say "Would open".
  - Verification: `$ uv run devops ci test tests/commands/test_pr_dry_run.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
