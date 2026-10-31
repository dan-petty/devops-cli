# Tasks

## 1. Domain Logic Extraction and Seams

- [x] Write failing tests for `telemetry/waterfall.py` profiling and polling functions: `uv run pytest tests/telemetry/test_trace_propagation.py`.
- [x] Move `_run_profiled_command` and `_read_trace_from_tempo` from `commands/telemetry.py` to `telemetry/waterfall.py` behind public functions `run_profiled_command` and `poll_trace_spans`; update `commands/telemetry.py` to delegate to them: `uv run pytest tests/telemetry/`.
- [x] Write failing test for `server/service.py` service mode configuration validation: `uv run pytest tests/server/test_server_service.py`.
- [x] Move `_validate_service_mode` and `_require_github_app` from `commands/serve.py` to `server/service.py` behind public function `validate_service_mode`; update `commands/serve.py` to delegate to it: `uv run pytest tests/server/test_server_service.py`.
- [x] In `server/service.py`, replace bare `time.time()` with `self.clock().timestamp()` in `_execute_scoped` and `_execute_batch`: `uv run pytest tests/server/test_server_service.py`.
- [x] In `ui/data_providers.py`, ensure Valkey uses `resolve_valkey_client`, Docker uses `get_engine().client()`, and Kubernetes uses `KubernetesService.get_instance().core_api()`: `uv run pytest tests/ui/`.
- [x] Regenerate documentation: `uv run devops docs generate --sync-readme`.

## 2. Test File Relocation, Splitting, and Cleanup

- [x] Relocate `tests/ai/test_output.py` to `tests/output/test_output.py`: `uv run pytest tests/output/test_output.py`.
- [x] Split `tests/ui/test_ui_reactive.py` into 24 behaviour-specific test files under `tests/ui/`, replace local finding builders with `make_finding` from `tests/support/builders.py`, remove redundant `@pytest.mark.asyncio`, and delete `tests/ui/test_ui_reactive.py`: `uv run pytest tests/ui/`.
- [x] Dissolve catch-all tests in `tests/telemetry/test_telemetry.py` and `tests/ui/test_ui_dashboard.py`: `uv run pytest tests/telemetry/test_telemetry.py tests/ui/test_ui_dashboard.py`.
- [x] Dissolve `tests/telemetry/test_otel_command_coverage.py` into telemetry behaviour tests over the OTLP fake, and verify `devops --help` command coverage in a dedicated CLI test: `uv run pytest tests/telemetry/`.
- [x] Migrate `tests/output/test_consolidation_table_builder.py` and `tests/security/test_network_security_and_trace_correlation.py` to their behaviour owners: `uv run pytest tests/output/ tests/security/`.
- [x] Convert table and document output assertions to syrupy snapshots where full output is the contract: `uv run pytest tests/output/`.
- [x] Regenerate documentation: `uv run devops docs generate --sync-readme`.

## 3. Invariants, Ratchets, and CI Verification

- [x] Remove any remaining internal monkeypatches and private imports in the migrated suites: `uv run pytest tests/invariants/test_source_tree.py`.
- [x] Verify diff-coverage >= 90% and run full test suites: `uv run devops ci test`.
- [x] Run full CI quality gate: `uv run devops ci`.
- [x] Regenerate documentation: `uv run devops docs generate --sync-readme`.
