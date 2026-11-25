# Tasks

## 1. Behavior (`behavior`)

- [x] 1.1 Write failing tests for `CreatedPull` reviewer parsing, `missing_pull_reviewers`, `GitHubClient.request_pull_reviewers`, `open_or_update` reviewer requests, `delivery_request` / `open_cmd` / dry-run request plans, and `devops repos onboard` template PR reviewer routing
  - Verification: `$ uv run pytest -q tests/github/test_github_client.py tests/roadmap/steps/test_roadmap_step_open.py tests/github/onboard/test_onboard_rows.py tests/github/onboard/test_onboard_routes.py`
- [x] 1.2 Implement `CreatedPull` reviewer fields, `missing_pull_reviewers`, and `request_pull_reviewers` in `src/devops_cli/github/client.py`, add `reviewers` support in `open.py` and callers (`open_row.py`, `stage.py`, `implement_phases.py`, `commands/roadmap_step_open.py`, `request_plan.py`, `messages.py`), and add `template-pull-reviewers` in `github/onboard/routes.py` and `template_pr.py`, updating affected stage/implement fake routes
  - Verification: `$ env -u GIT_EDITOR uv run pytest -q tests/github/ tests/roadmap/steps/test_roadmap_step_open.py tests/roadmap/stage/ tests/roadmap/implement/ tests/roadmap/test_roadmap_dry_runs.py tests/roadmap/test_roadmap_open_row.py tests/roadmap/test_roadmap_run_row_faults.py tests/invariants/ tests/telemetry/test_roadmap_stage_steps.py tests/core/test_roadmap_implement_planned_run.py tests/commands/test_roadmap_step_open.py -k "not _repeated_at"`

## 2. Workflows, config, and documents

- [x] 2.1 Remove `"automerge": false` from `seaweedfs` in `.github/renovate.json` and update `k8s/README.md` so approved SeaweedFS updates auto-merge after checks pass
  - Verification: `$ renovate-config-validator --strict --no-global .github/renovate.json`
- [x] 2.2 Add `Request review on the release pull request` step to `.github/workflows/release.yml` and assert it in `tests/invariants/test_workflow_contracts.py`
  - Verification: `$ uv run pytest -q tests/invariants/test_workflow_contracts.py && uv run devops ci --check --only actionlint,zizmor`

## 3. Verification

- [x] 3.1 Confirm generated CLI docs are up to date, run `devops openspec check`, archive the change, and run static CI gates
  - Verification: `$ uv run devops docs generate --check && uv run devops openspec check && uv run devops ci --check --no-cache --only format,actionlint,zizmor,docs,test-tree,startup-imports,swallowed-failures,domain`

Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
