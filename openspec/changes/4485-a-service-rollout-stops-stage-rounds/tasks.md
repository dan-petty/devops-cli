# Tasks

## 1. No new round, row or item once the Service stops

Kind: behavior.

- [ ] 1.1 Add failing tests: a round in flight at the stop runs to its end and no round starts for the pending trigger (`tests/server/test_server_service.py`); no row starts after the stop and the next round runs it (`tests/roadmap/test_roadmap_run_job_counts.py`); the stage job plans no next item after the stop (`tests/roadmap/stage/test_roadmap_stage_item_writes.py`); the refine job refines no next item after the stop (`tests/roadmap/refine/test_roadmap_refine_round.py`). Replace the test that the drain runs the pending triggers.
  - Verification: `$ uv run devops ci test tests/server/test_server_service.py tests/roadmap/test_roadmap_run_job_counts.py tests/roadmap/stage/test_roadmap_stage_item_writes.py tests/roadmap/refine/test_roadmap_refine_round.py`
- [ ] 1.2 Add `roadmap/service_stop.py` with the process-wide stop and register its reset in `tests/conftest.py`. The worker pops no batch once it is told to stop; `_execute_due_rows` starts no due row once the Service stops and ends the round with the stop (the error raise moves to `_raise_for_rows`); `_plan_each` and `plan_refine` start no next item. Add `MESSAGES.serve.stop_before_work`.
  - Verification: `$ uv run devops ci test tests/server/test_server_service.py tests/roadmap/test_roadmap_run_job_counts.py tests/roadmap/stage/test_roadmap_stage_item_writes.py tests/roadmap/refine/test_roadmap_refine_round.py`

## 2. A bounded drain, then a cut

Kind: behavior.

- [ ] 2.1 Add failing tests: a cut budget refuses a request that the window has room for (`tests/github/test_service_limits.py`); a round still in flight at the end of the drain wait ends at its next GitHub request as `stopped`, and the Service logs the cut (`tests/server/test_server_service.py`).
  - Verification: `$ uv run devops ci test tests/github/test_service_limits.py tests/server/test_server_service.py`
- [ ] 2.2 Add `RequestBudget.cut`. `drain_and_stop` sets the stop, stops the workers, joins them within `drain_seconds`, then cuts the budget and joins them within `cut_seconds`. `ServiceManager` takes both, with `CONST_SERVICE_STOP_DRAIN_SECONDS` (600) and `CONST_SERVICE_STOP_CUT_SECONDS` (30) as defaults. Add `MESSAGES.serve.budget_cut` and `MESSAGES.serve.drain_cut`.
  - Verification: `$ uv run devops ci test tests/github/test_service_limits.py tests/server/test_server_service.py`

## 3. The grace period and the removed setting

Kind: behavior.

- [ ] 3.1 Add a failing test that the Service pod's grace period is `CONST_SERVICE_STOP_GRACE_SECONDS`, more than the two waits together, and that its container has no lifecycle hook (`tests/server/routes/test_k8s_roadmap_service.py`).
  - Verification: `$ uv run devops ci test tests/server/routes/test_k8s_roadmap_service.py`
- [ ] 3.2 Set `terminationGracePeriodSeconds: 660` in `k8s/devops/roadmap-service/deployment.yaml` and add `CONST_SERVICE_STOP_GRACE_SECONDS`. Delete `service.drain_timeout_seconds`, `DEFAULT_SERVICE_DRAIN_TIMEOUT_SECONDS`, the ConfigMap key in `k8s/configmap.py` and their test cases.
  - Verification: `$ uv run devops ci test tests/server/routes/test_k8s_roadmap_service.py tests/k8s/test_k8s_configmap.py tests/commands/test_config_field_validation.py tests/security/test_config_declarations.py`

## 4. Documentation

Kind: documents.

- [ ] 4.1 Describe the bounded stop in `k8s/README.md` (Roadmap service item 21 and the Stop switch), remove the setting from its ConfigMap table, and regenerate `docs/CONFIGURATION.md` and `docs/ENV_VARS.md` with `uv run devops docs generate --sync-readme`.
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: after the merge, delete the line `drain_timeout_seconds: 120` from `config.yaml` and from the live ConfigMap `devops/devops-cli-config`. The Service ignores the key, so the order does not matter.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
