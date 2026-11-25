# Tasks

## 1. Behavior

Kind: behavior. Reads: `src/devops_cli/openspec/scaffold.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/pull_describe.py`, `tests/openspec/test_openspec_new.py`, `tests/commands/test_pr_describe.py`. Changes: `src/devops_cli/openspec/scaffold.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/pull_describe.py`, `tests/openspec/test_openspec_new.py`, `tests/commands/test_pr_describe.py`.

- [x] 1.1 Write failing tests in `tests/openspec/test_openspec_new.py` and `tests/commands/test_pr_describe.py` verifying that `scaffold_proposal` omits any closing keyword while citing the issue, `devops pr describe` drops closing clauses naming the delivered issue (`and closes #5434.`), and `devops pr describe` still refuses closing keywords naming another issue (`Closes #9999.`)
  - Verification: `$ uv run devops ci test tests/openspec/test_openspec_new.py tests/commands/test_pr_describe.py`
- [x] 1.2 Remove `Closes #{issue}.` from `scaffold_proposal`, add `strip_closing_keyword(text, issue)` in `src/devops_cli/roadmap/stage/stage_change.py`, and apply it to the delivered issue in `src/devops_cli/roadmap/pull_describe.py`
  - Verification: `$ uv run devops ci test tests/openspec/test_openspec_new.py tests/commands/test_pr_describe.py`

## 2. Documents

Kind: other. Reads: `docs/CLI_REFERENCE.md`, `docs/commands/pr.md`. Changes: `openspec/specs/openspec-scaffold/spec.md`, `openspec/specs/pull-request-form/spec.md`.

- [x] 2.1 Verify CLI docs stay current and run OpenSpec checks
  - Verification: `$ uv run devops ci docs && uv run devops openspec check`
