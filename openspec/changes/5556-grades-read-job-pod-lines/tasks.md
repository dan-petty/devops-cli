# Tasks

## 1. The grades read the result lines of each Job pod

Kind: behavior.

- [x] 1.1 Add the fake Loki `tests/support/fakes/loki.py`, and the tests of the report on one JSON line of the Service, one plain line of a fix-plan Job, one plain line of a stage Job and one line of a runner pod
  - Verification: `$ uv run devops ci test tests/roadmap/test_job_grade_report.py` fails on the base
- [x] 1.2 Put the selector and the parse of both forms in `RESULT_LINES` of `job_grade_report.py`, and start each query with it
  - Verification: `$ uv run devops ci test tests/roadmap/test_job_grade_report.py tests/commands/test_roadmap_eval_grades.py`

## 2. The stage Job writes one result line after its check-in

Kind: behavior.

- [ ] 2.1 Add the tests of the line of the stage Job on stderr, after the check-in, and of no line when the check-out names another Job or the check-in fails
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job_entry.py` fails on the base
- [ ] 2.2 Move the stderr handler of the fix-plan command to `job_lines_to_stderr` of `job_result.py`, use it in `devops roadmap stage --job-item`, and log the result line of the Job after its check-in
  - Verification: `$ uv run devops ci test tests/roadmap/stage tests/commands/test_roadmap_step_fix_plan.py tests/roadmap/test_job_result.py`

## 3. The dashboard reads the same lines

Kind: manifest.

- [ ] 3.1 Add the test that each query of the row `Roadmap Job Success` starts with `RESULT_LINES`, and change the four queries of `k8s/devops/dashboards/devops-cli.json`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_dashboards.py tests/grafana`

## 4. Documents

Kind: documents.

- [ ] 4.1 Update the query, the two forms of a line and the attempts that write no line in `docs/roadmap/job-success.md`, and the end of the stage Job in `docs/roadmap/stage.md` and `docs/CLUSTER.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: after the release, run `devops roadmap eval grades --window 7d` and see the `fix_plan` attempts that Loki holds and the attempts of the stage Jobs of the new image.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
