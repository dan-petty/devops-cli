# Implementation Tasks

## 1. Classify Review Commands and Implement Request Plans
- [x] 1.1 Create `src/devops_cli/review/review_plans.py` with request plan builders for review commands (`uv run pytest tests/commands/test_review_dry_run.py`)
- [x] 1.2 Update `src/devops_cli/commands/review.py` to decorate callbacks with dry-run classes, wire request plans, and add local preview to `export-feedback` (`uv run pytest tests/commands/test_review_dry_run.py`)
- [x] 1.3 Remove echo-only previews and `--dry-run` from `review rules test` without a shim (`uv run pytest tests/commands/test_review_rules_pack.py`)
- [x] 1.4 Remove all 20 review command paths and their `ai review` aliases from `tests/fixtures/dry_run_gaps.json` (`uv run pytest tests/invariants/test_dry_run_class_ratchet.py`)

## 2. Verification and Documentation
- [x] 2.1 Add comprehensive unit tests in `tests/commands/test_review_dry_run.py` asserting request plans and zero network calls under dry run (`uv run pytest tests/commands/test_review_dry_run.py`)
- [x] 2.2 Synchronize documentation with `uv run devops docs generate --sync-readme`
- [x] 2.3 Run full fast static checks with `uv run devops ci --check --no-cache --skip test,outdated,actionlint`
