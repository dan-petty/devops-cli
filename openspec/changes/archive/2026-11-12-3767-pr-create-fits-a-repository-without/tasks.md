# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests: `pr create` in a repository without `openspec/config.yaml` opens a draft from `--head` with the body as given, a repository with the file keeps the body rules, the base branch decides, the REST fallback posts `--head`, and a dry run for another repository checks no body; `pr ready` marks a pull request with no checks ready in a repository with no workflow, waits in a repository with workflows, and stops when the workflows cannot be read
  - Verification: `$ uv run devops ci test tests/commands/test_pr_other_repository.py`
  - Verification: `$ uv run devops ci test tests/commands/test_pr.py -k "exits_on_the_checks or nothing_to_wait"`
- [x] 1.2 Add `repository_uses_openspec` to `src/devops_cli/openspec/project.py`, with a test that only a missing file reads as False, and let the in-memory store fail `repository_file`
  - Verification: `$ uv run devops ci test tests/openspec/test_openspec_project.py`
- [x] 1.3 Check the body in `_form_checked` only where the base branch holds `openspec/config.yaml`, take the switch from the checkout in a dry run without `--repo`, and add `--head` to `pr create`, `pr_create_args`, `plan_pr_create` and the REST fallback
  - Verification: `$ uv run devops ci test tests/commands/test_pr_other_repository.py tests/commands/test_pr_form_check.py tests/commands/test_pr_cmd.py tests/commands/test_pr_dry_run.py`
- [x] 1.4 Add `GitHubClient.count_workflows`, `CheckVerdictSummary.reports_nothing` and `no_checks_reported`, and let `pr ready` skip the checks and the pending-check warning when the head commit reports no check and the repository has no workflow
  - Verification: `$ uv run devops ci test tests/commands/test_pr.py tests/github/test_pr_check_verdict.py tests/github/test_merge_readiness.py`

## 2. Documents

- [x] 2.1 State the rules in the help of `pr create` and `pr ready`, regenerate the command documents, and update `CONTRIBUTING.md` section 4 and the skill `devops-pr-ci`
  - Verification: `$ uv run devops ci --check --only docs`
