# Tasks

## 1. Reduce grade query label cardinality and split count windows on Loki series limit

Kind: behavior. Reads: `src/devops_cli/roadmap/job_grade_report.py`, `src/devops_cli/k8s/logql.py`, `src/devops_cli/models/prometheus.py`, `tests/roadmap/test_job_grade_report.py`, `tests/support/fakes/loki.py`. Changes: `src/devops_cli/roadmap/job_grade_report.py`, `tests/roadmap/test_job_grade_report.py`, `tests/support/fakes/loki.py`.

- [x] 1.1 Add failing tests in `tests/roadmap/test_job_grade_report.py` covering `| keep` label sets on all `GradeQueryKind` queries, window splitting and summation when Loki returns HTTP 400 `maximum number of series`, and non-splitting on other HTTP 400 errors.
  - Verification: `$ uv run devops ci test tests/roadmap/test_job_grade_report.py tests/commands/test_roadmap_eval_grades.py`
- [x] 1.2 Add `| keep` clauses in `src/devops_cli/roadmap/job_grade_report.py`, add recursive window splitting and `_sum_query_results` for count queries rejected on the series limit, and add `| keep` stage support to `LokiFake` in `tests/support/fakes/loki.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_job_grade_report.py tests/commands/test_roadmap_eval_grades.py`

## 2. Update job success documentation

Kind: other. Reads: `docs/roadmap/job-success.md`. Changes: `docs/roadmap/job-success.md`.

- [x] 2.1 Update `docs/roadmap/job-success.md` to document that `eval grades` keeps only used labels and halves/sums rejected count windows down to `1h` when Loki hits the 500-series limit.
  - Verification: `$ uv run devops ci docs`
