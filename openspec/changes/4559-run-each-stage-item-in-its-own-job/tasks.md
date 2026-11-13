# Tasks

## 1. The submit and the recovery of the stage Jobs

Kind: behavior.

- [x] 1.1 Add `tests/roadmap/stage/test_roadmap_stage_submit.py` (lane, limit, 409, check-out order, failed create, recovery of each end, free evictions, split, orphan first), `tests/roadmap/stage/test_roadmap_stage_kill.py` and the API tests of 409, labels and the reason of a failure
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_submit.py tests/k8s/test_k8s_cluster_job_api.py` fails on the base
- [x] 1.2 Add `stage_submit.py`, the setting `roadmap.stage.jobs`, the record key `stage.evictions`, `ClusterJobExistsError`, the labels and the failure reason of `ClusterJob`, the rule `stage_job` of the selection, `read_stage_round`, the counted check-in, and move the row to the status lane with no in-pod path
  - Verification: `$ uv run devops ci test tests/roadmap/stage tests/roadmap/test_roadmap_run_due_table.py tests/roadmap/test_roadmap_run_lanes.py tests/k8s`

## 2. Telemetry

Kind: manifest.

- [x] 2.1 Add the rule test of the stage series, the promtool cases of `job="roadmap-stage"` and the selector test of the job grades
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py tests/roadmap/test_job_grade_report.py` fails on the base
- [x] 2.2 Widen the rule selectors, the job grade selector and the dashboard queries, and chart `devops_cli_service_stage_jobs_total`
  - Verification: `$ uv run devops ci test tests/prometheus tests/grafana tests/telemetry`

## 3. Documents

Kind: documents.

- [x] 3.1 Update `docs/CLUSTER.md` (step 15, lanes, Stage Jobs), `docs/roadmap/stage.md`, `docs/roadmap/job-success.md`, `docs/roadmap/intake.md` and `docs/ROADMAP_WORKFLOW.md`, and regenerate the references
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: after the release, the live proof of #4559: the stage Jobs run on the next Ready items for 7 days, 0 stage attempts stop at a Service restart, and the hop from Ready to the Job is one status-lane interval or less outside the rollout windows.
- Pending a person: state the cold-cache GitHub requests of the live run of part 1 (`devops_cli_github_requests_total{job="roadmap-stage"}`) against the 3,357 a day of the stage row, and set `roadmap.stage.github_requests_per_hour` from it.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
