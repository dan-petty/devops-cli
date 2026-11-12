# Tasks

## 1. The result line (behavior)

- [x] 1.1 Write failing tests: a line holds every field in order, a value with issue text becomes `other`, and each intended result is a result of its job.
  - Verification: `$ uv run devops ci test tests/roadmap/test_job_result.py`
- [x] 1.2 Add `src/devops_cli/roadmap/job_result.py` with `RoadmapJob`, `SUCCESS_RESULTS`, `INFRA_CLASSES` and `log_job_result`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_job_result.py`

## 2. Each job logs its attempts (behavior)

- [x] 2.1 Write failing tests: a stage round of three tried items gives three lines, an ended implement Job gives one line, a refine round, a review, an alternatives check and an intake round each give one line for each attempt.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job_result.py tests/roadmap/implement/test_roadmap_implement_job_result.py tests/roadmap/refine/test_roadmap_refine_job_result.py tests/roadmap/test_roadmap_alternatives_job_result.py tests/roadmap/intake/test_roadmap_intake_job_result.py`
- [x] 2.2 Call `log_job_result` from `emit_stage_results` (`stage.py`), `_report` (`implement_submit.py`), `RefineWriter.settle` (`refine.py`), `judge` (`refine_judge.py`), `AlternativesWriter.settle` (`alternatives.py`) and `_count_candidate` (`intake.py`). Keep the counts of each stage item in `_Planner`, and read the end time of a Job in `ClusterJob`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job_result.py tests/roadmap/implement/test_roadmap_implement_job_result.py tests/roadmap/refine/test_roadmap_refine_job_result.py tests/roadmap/refine/test_roadmap_refine_trust.py tests/roadmap/test_roadmap_alternatives_job_result.py tests/roadmap/test_roadmap_alternatives_one_write.py tests/roadmap/test_roadmap_alternatives_recheck.py tests/roadmap/intake/test_roadmap_intake_job_result.py`

## 3. The dashboard and the documents (other)

- [x] 3.1 Add the row `Roadmap Job Success` to `k8s/monitoring/dashboards/devops-cli.json`.
  - Verification: `$ uv run devops grafana dashboards lint k8s/monitoring/dashboards/devops-cli.json`
- [x] 3.2 Write `docs/roadmap/job-success.md` with the line, the intended results, the query and the 80% rule.
  - Verification: `$ uv run devops ci docs`
