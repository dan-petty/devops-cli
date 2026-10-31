# Tasks

## 1. Configure Gateway Models and Fallbacks

Reads: None.. Changes: None..

- [x] 1.1 Add `devops-triage` deployment and fallbacks to `k8s/llm/gateway/config.yaml`, update `tests/test_k8s_llm_gateway.py`, and verify with `uv run pytest tests/test_k8s_llm_gateway.py`.
- [x] 1.2 Update `k8s/devops/configmap.example.yaml` with `triage.model: devops-triage`.

## 2. Add Triage Task Setting and Intake Model Client

Reads: None.. Changes: None..

- [x] 2.1 Add `triage: AITaskOverride` to `AITasksConfig` in `src/devops_cli/config/settings.py`.
- [x] 2.2 Update `GatewayIntakeModel._client` in `src/devops_cli/roadmap/intake_model.py` to use `task="triage"` and `self._ai.for_task("triage")`.
- [x] 2.3 Add test for setting and unsetting `ai.tasks.triage` in `tests/test_roadmap_intake.py`, and verify with `uv run pytest tests/test_roadmap_intake.py -k triage`.

## 3. Implement Triage Lane and Cross-Lane Refine

Reads: None.. Changes: None..

- [x] 3.1 Declare constants `CONST_SERVICE_LANE_TRIAGE`, `CONST_ROADMAP_RUN_TRIAGE_CLONE_DIRNAME`, and `CONST_ROADMAP_REFINE_DUE_STAMP` in `src/devops_cli/config/constants.py`.
- [x] 3.2 Define `TRIAGE_LANE_ROWS` and remove `intake` from `MODEL_LANE_ROWS` in `src/devops_cli/roadmap/run.py`. Update `DEFAULT_DUE_TABLE` and `_SCOPED_INTAKE`.
- [x] 3.3 Implement cross-lane refine stamp writing in `_run_intake_adapter` / `_intake_one` and check in `_Poll.is_due` in `src/devops_cli/roadmap/run.py`.
- [x] 3.4 Update `service_jobs` to include the `triage` lane.
- [x] 3.5 Add tests in `tests/test_roadmap_run.py` for cross-lane refine, request budget across three lanes, and triage queue-depth metrics with webhook trigger. Verify with `uv run pytest tests/test_roadmap_run.py`.

## 4. Documentation and Docs Generation

Reads: None.. Changes: None..

- [x] 4.1 Update `CONTEXT.md` to drop triage from avoid lists and describe three lanes.
- [x] 4.2 Update `serve --service` help text in `src/devops_cli/lang/en/help.py`, and regenerate docs with `uv run devops docs generate --sync-readme`.
- [x] 4.3 Update `k8s/README.md` to document the `devops-triage` model and three service lanes.

## 5. Verification and OpenSpec Archive

Reads: None.. Changes: None..

- [x] 5.1 Run full CI test suite and linters to verify all checks pass.
- [x] 5.2 Archive the change folder with `PATH="/home/vscode/.local/bin:$PATH" uv run devops openspec archive 1534-intake-triage-lane`.
