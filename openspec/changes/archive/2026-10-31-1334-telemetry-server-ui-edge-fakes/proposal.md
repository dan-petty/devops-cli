# Proposal

## Why

Issue #1334 delivers the Phase E test migration for `telemetry/`, `server/`, `ui/`, `output/`, and `docs/` packages under parent issue #1307. Tests currently patch devops-cli internal names and import private names across these packages. Production logic that belongs in domain packages resides in command modules: `_run_profiled_command` and `_read_trace_from_tempo` in `commands/telemetry.py`, and `_validate_service_mode` in `commands/serve.py`. `test_ui_reactive.py` is an oversized 2,890-line monolith spanning 24 distinct behaviour sections with redundant `@pytest.mark.asyncio` markers and a local finding builder. `test_output.py` resides erroneously under `tests/ai/`, catch-all test files exist, and output assertions do not use standard snapshot testing.

## What Changes

- Move profiled execution and Jaeger trace polling from `src/devops_cli/commands/telemetry.py` to `src/devops_cli/telemetry/waterfall.py` behind public functions, and delegate CLI command logic to them.
- Move service mode validation and webhook secret parsing from `src/devops_cli/commands/serve.py` to `src/devops_cli/server/service.py` behind a public function `validate_service_mode`.
- In `src/devops_cli/ui/data_providers.py`, ensure Kubernetes, Docker, and Valkey access go through domain seams (`KubernetesService`, `DockerEngineService`, `resolve_valkey_client`).
- In `src/devops_cli/server/service.py`, ensure timestamp reads use `self.clock().timestamp()` rather than bare `time.time()`.
- Move `tests/ai/test_output.py` to `tests/output/test_output.py` to mirror the package tree.
- Split `tests/ui/test_ui_reactive.py` into distinct behaviour test files under `tests/ui/` matching its 24 behaviour sections, and remove `test_ui_reactive.py`.
- Replace the local finding builder in UI tests with `make_finding` from `tests/support/builders.py`.
- Dissolve catch-all test functions in `test_output.py`, `test_telemetry.py`, and `test_ui_dashboard.py`.
- Dissolve `test_otel_command_coverage.py`: route span and metric tests to telemetry behaviour tests over the OTLP fake, and verify `devops --help` in CLI tests.
- Rename or dissolve `test_consolidation_table_builder.py` and `test_network_security_and_trace_correlation.py` into their respective behaviour owners.
- Replace manual output string comparisons with syrupy snapshots for formatter tables, dashboard views, and generated documentation contracts.
- Remove redundant module-level `CliRunner()` instances and redundant `@pytest.mark.asyncio` markers across the 27 affected test files.
- Ensure all tests double only process edges through shared fakes (`cli`, `process_fake`, `otlp_fake`, `keyring_fake`, `fake_k8s`, `docker_engine_fake`, `valkey_fake`).
- This change alters internal test organization and refactors command helpers into domain packages without changing consumer-facing CLI syntax, options, or outputs, so it sets `skip_specs: true`.
- This change fits one pull request.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `src/devops_cli/telemetry/waterfall.py`: exports `run_profiled_command` and `read_trace_spans_with_polling`.
- `src/devops_cli/commands/telemetry.py`: delegates profiling and polling to `telemetry.waterfall`.
- `src/devops_cli/server/service.py`: exports `validate_service_mode`, uses `clock` for timestamp metrics.
- `src/devops_cli/commands/serve.py`: delegates service mode validation to `server.service`.
- `src/devops_cli/ui/data_providers.py`: uses `resolve_valkey_client` and `KubernetesService`.
- `tests/ui/`: `test_ui_reactive.py` is decomposed into 24 behaviour test modules; uses `make_finding`.
- `tests/output/`: contains `test_output.py` moved from `tests/ai/`, uses syrupy snapshots.
- `tests/telemetry/`: dissolved catch-alls; OTLP fake usage without patching `_send_payload`.

## Feasibility

- AST inspection and grep confirmed the exact patch sites, private imports, and command logic locations.
- Running `uv run pytest tests/ui/` and `uv run pytest tests/telemetry/` exercises the existing suites.
- Syrupy is already an installed test dependency (`syrupy` in `pyproject.toml`).

## Existing Tool Considered

Standard test tools and existing edge fakes cover all requirements:
- `syrupy` for snapshot testing of table outputs and documents.
- `time-machine` and clock parameters for time control.
- `tests/support/fakes/` (`OTLPFake`, `ProcessFake`, `KeyringFake`, `DockerEngineFake`, `KubernetesFake`, `ValkeyFake`).
- `tests/support/builders.py` (`make_finding`).

Deleted internal code:
- Redundant local finding builder in UI tests.
- Internal monkeypatch targets (`_send_payload`, `_send_payload_sync`).
- Catch-all test files and monolithic `test_ui_reactive.py`.
