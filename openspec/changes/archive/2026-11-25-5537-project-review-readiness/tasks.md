# Tasks

## 1. Readiness report tests

- [x] 1.1 Write failing unit and integration tests for `READINESS_ROWS` guideline sync, Scorecard JSON mapping, `service.repos`/`infra.repos` Scorecard subprocess execution, GitHub contents queries, command checks, `manual` rows, `--ref`, private repo exclusion/fallback, `--dry-run`, and guideline text
  - Verification: `$ uv run pytest -n 0 tests/roadmap/project_review/test_readiness.py`

## 2. Implementation & CLI integration

- [x] 2.1 Implement `src/devops_cli/roadmap/project_review/readiness.py`, add `BIN_SCORECARD` in `src/devops_cli/config/commands.py`, add optional `paginate` to `read_github` in `src/devops_cli/roadmap/project_review/readers.py`, extend `ReviewData` in `src/devops_cli/roadmap/project_review/data.py`, wire into `review.py` and `commands/roadmap_review.py` (`--ref`), and add catalog help/messages
  - Verification: `$ uv run pytest -n 0 tests/roadmap/project_review/ tests/commands/test_roadmap_review.py`

## 3. Documents and checks

- [x] 3.1 Update `docs/guidelines/production-readiness.md` Readiness record section and regenerate CLI docs (`uv run devops docs generate`)
  - Verification: `$ uv run devops ci --check --skip test`

Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
