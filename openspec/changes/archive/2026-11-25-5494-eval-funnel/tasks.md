# Tasks

## 1. Behavior

<!-- kind: behavior -->

- [x] 1.1 Write failing unit and CLI tests for `devops roadmap eval funnel` covering ISO-week cohorts with `unlabeled` cancellation, `G1` vs `continue` paths, Wilson bounds and smallest change, median/p90 durations, young `in progress` exclusion, Loki token/cost division, missing result-line counts, New-to-staged tokens, option validation, `--json`, and `--dry-run`
  - Verification: `$ uv run devops ci test tests/roadmap/test_job_funnel.py tests/commands/test_roadmap_eval_funnel.py`
- [x] 1.2 Implement funnel evaluation logic (`src/devops_cli/roadmap/job_funnel.py`), CLI command (`src/devops_cli/commands/roadmap_eval_funnel.py`, registered in `src/devops_cli/commands/roadmap_eval.py`), and language strings (`src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`)
  - Verification: `$ uv run devops ci test tests/roadmap/test_job_funnel.py tests/commands/test_roadmap_eval_funnel.py`

## 2. Documents

<!-- kind: documents -->

- [x] 2.1 Document `devops roadmap eval funnel` in `docs/roadmap/job-success.md` and regenerate generated CLI documentation via `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Run `devops roadmap eval funnel` live against `dan-petty/devops-cli` for the last 28 days in a cluster runner Job as the App after release and post the Phase 0 base on `#5494` (`#6256`).
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
