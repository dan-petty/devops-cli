# Tasks

## 1. Gh project, views and pages dry-run plans

Reads: `src/devops_cli/commands/gh.py`, `src/devops_cli/github/projects.py`, `src/devops_cli/github/pages.py`, `tests/fixtures/dry_run_gaps.json`.. Changes: `src/devops_cli/commands/gh.py`, `src/devops_cli/github/projects.py`, `src/devops_cli/github/pages.py`, `tests/fixtures/dry_run_gaps.json`, `tests/test_gh_project_views_pages_dry_run.py`..

- [x] 1.1 Write failing unit tests in `tests/test_gh_project_views_pages_dry_run.py` validating that the 10 request-making commands have request plans and make no external calls under `--dry-run`, and that the 5 local commands execute safely under `devops --dry-run <command>`.
- [x] 1.2 Implement request builders in `src/devops_cli/github/pages.py` for `gh pages status`, `gh pages builds`, and `gh pages build`.
- [x] 1.3 Implement request builders in `src/devops_cli/github/projects.py` for `gh project audit`, `gh project link`, `gh project list`, `gh project sync`, `gh project workflows list`, `gh views audit`, and `gh views sync`.
- [x] 1.4 Update callbacks in `src/devops_cli/commands/gh.py`: apply `@dry_run_class("no-external-request")` to the 5 local commands; add `--dry-run` and `@dry_run_class("request-plan")` to the 10 commands with request plans.
- [x] 1.5 Remove all 15 commands from `tests/fixtures/dry_run_gaps.json`.
- [x] 1.6 Verify that all tests pass, docs are up to date (`uv run devops docs generate --sync-readme`), and `uv run devops ci` passes.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
