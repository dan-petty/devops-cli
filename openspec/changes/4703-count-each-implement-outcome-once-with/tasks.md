# Tasks

## 1. Count each implement outcome once with its repository

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_submit.py`. Changes: the same file, `src/devops_cli/lang/en/messages.py` and `tests/roadmap/implement/test_roadmap_implement_submit.py`.

- [x] 1.1 Add the failing tests `test_a_stop_that_the_runner_wrote_and_exited_zero_counts_once_as_a_failed_attempt`, `test_the_job_of_an_item_that_closed_before_the_report_counts_once_and_stops_nothing`, `test_a_closed_item_whose_job_the_cluster_no_longer_holds_is_not_reported` and `test_a_round_with_no_repository_is_refused_before_any_request`, and give the success of `test_job_reporting_emits_pipeline_outcome_metrics_and_repair_rounds_and_tokens` the runner result `ready`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Count the result `failed` for an attempt with a failure class, report the Job of a closed item that the cluster holds with no stop, and refuse an empty `repo` in `run_implement_round`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py`

## 2. Document the result label

Kind: documents. Reads: `k8s/README.md`. Changes: `k8s/README.md`.

- [x] 2.1 Say in `k8s/README.md` that the `result` of `devops_cli_service_implement_jobs_total` is `failed` for a Job that left a stop, and the state of the Job otherwise
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
- Pending a person: 7 days after the deploy, compare `sum(increase(devops_cli_service_implement_jobs_total{job="roadmap-service"}[7d]))` with the runner Jobs that kube-state-metrics shows as started in the same 7 days. The difference must be 10% or less.
