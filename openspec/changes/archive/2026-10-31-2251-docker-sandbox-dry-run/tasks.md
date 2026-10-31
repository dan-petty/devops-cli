# Tasks

## 1. Plan Generators and Docker Commands Dry Run

- [x] 1.1 Write failing unit tests for docker command dry runs in `tests/commands/test_docker_dry_run.py` verifying classification, plan structure, and zero external daemon/subprocess execution. Verify with `uv run devops ci test tests/commands/test_docker_dry_run.py`.
- [x] 1.2 Implement plan builders in `src/devops_cli/docker/docker_plans.py` for docker commands (`images`, `build`, `stats`, `prune`, `cache`, `push`, `sign`, `verify`, `sandbox`). Verify with `uv run pytest tests/commands/test_docker_dry_run.py`.
- [x] 1.3 Decorate the 9 docker commands with `@dry_run_class("request-plan")`, wire dry-run handlers to render request plans, remove legacy `render_dry_run_result` calls, and regenerate docs. Verify with `uv run devops docs generate --sync-readme`.

## 2. Sandbox Plan Generators and Commands Dry Run

- [x] 2.1 Write failing unit tests for sandbox command dry runs in `tests/commands/test_sandbox_dry_run.py` verifying classification, plan output, and zero external daemon/HTTP/DNS execution. Verify with `uv run devops ci test tests/commands/test_sandbox_dry_run.py`.
- [x] 2.2 Implement plan builders in `src/devops_cli/sandbox/sandbox_plans.py` for sandbox commands (`deploy`, `stop`, `status`, `logs`, `exec`, `probe`, `network-policy`, `metrics`, `traces`). Verify with `uv run pytest tests/commands/test_sandbox_dry_run.py`.
- [x] 2.3 Decorate the 9 sandbox commands with `@dry_run_class("request-plan")`, wire dry-run handlers to render request plans, remove legacy echo-only previews, and regenerate docs. Verify with `uv run devops docs generate --sync-readme`.

## 3. Ratchet Gap Removal and Verification

- [x] 3.1 Remove all 18 docker and sandbox command entries from `tests/fixtures/dry_run_gaps.json` and verify the dry-run ratchet passes. Verify with `uv run pytest tests/invariants/test_dry_run_class_ratchet.py`.
- [x] 3.2 Update existing test fixtures and assertions where mock commands expected legacy dry-run echoes. Verify with `uv run pytest tests/commands/test_docker.py tests/commands/test_sandbox.py tests/test_security_sandbox_and_protection.py`.
- [x] 3.3 Run full quality gates and static checks. Verify with `uv run devops ci --check --skip outdated,actionlint`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
