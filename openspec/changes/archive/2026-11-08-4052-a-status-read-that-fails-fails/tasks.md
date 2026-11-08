# Tasks

## 1. Split the status reads into rows of their own

Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/telemetry/service_status.py`, `tests/roadmap/test_roadmap_status_rows.py`. Changes: `src/devops_cli/roadmap/run.py`, `tests/roadmap/test_roadmap_status_rows.py`, `tests/roadmap/test_roadmap_run_metrics.py`, `tests/roadmap/test_roadmap_run_failure_ledger.py`, `tests/roadmap/test_roadmap_run_lanes.py`, `tests/roadmap/test_roadmap_run_due_table.py`, `tests/roadmap/test_roadmap_run_job_rows.py`, `tests/roadmap/test_roadmap_run_service.py`, `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/roadmap/stage/test_roadmap_stage_ready.py`, `tests/support/roadmap_run.py`.

- [x] 1.1 Write `tests/roadmap/test_roadmap_status_rows.py` (`row_names`, `source_failed`, `ledger_per_row`, the row that sends its own gauge, the metrics row that raises), and change the row lists of the existing tests to the six rows. Run them and see them fail
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main` fails on the base and passes on the branch
- [x] 1.2 In `src/devops_cli/roadmap/run.py`, remove the three `except Exception` blocks of `_run_metrics_adapter` and the two status reads from it. Add `_run_github_status_adapter` and `_run_cloudflare_status_adapter`, each fetching one page and emitting its gauge. Add the rows `github_status` and `cloudflare_status` (`needs_clone=False`, `first_run_due=True`, the interval of `metrics`) after `release_comments` in `STATUS_LANE_ROWS`. Update the docstrings of the three runners, of `STATUS_LANE_ROWS` and of `build_stub_table`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_status_rows.py tests/roadmap/test_roadmap_run_metrics.py tests/roadmap/test_roadmap_run_failure_ledger.py tests/roadmap/test_roadmap_run_lanes.py tests/roadmap/test_roadmap_run_due_table.py tests/roadmap/test_roadmap_run_job_rows.py tests/roadmap/test_roadmap_run_service.py tests/roadmap/implement/test_roadmap_implement_submit.py tests/roadmap/stage/test_roadmap_stage_ready.py` passes

## 2. Name the new rows in the documents

Reads: `k8s/README.md`, `CONTEXT.md`, `openspec/specs/roadmap-implement-job/spec.md`. Changes: `k8s/README.md`, `CONTEXT.md`.

- [x] 2.1 In item 17 of `k8s/README.md`, list the rows `metrics`, `implement`, `stage_ready`, `release_comments`, `github_status` and `cloudflare_status` of the status lane, and say what `metrics`, `github_status` and `cloudflare_status` read and that a failed read fails its own row. In `CONTEXT.md`, add the two rows to the sentence about the status lane. Fix item 16 if it still says that `metrics` reads the status pages
  - Verification: `$ grep -q 'github_status' openspec/specs/roadmap-implement-job/spec.md && grep -q 'cloudflare_status' k8s/README.md` (the spec holds the rows once the change is archived)
- [x] 2.2 Check that the example ConfigMap still loads into `Settings` and that no document names a status read as part of the row `metrics`
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_configmap_keys.py tests/invariants/test_configmap_rollout_rule.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
