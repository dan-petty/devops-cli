# Tasks

## 1. The Ollama slot wait is a histogram by priority and outcome

- [x] 1.1 Write the failing tests `test_a_call_with_a_free_slot_observes_its_wait_by_priority`, `test_a_call_that_waits_for_a_held_slot_observes_the_wait` and `test_an_as_available_call_with_no_free_slot_observes_a_timeout` in `tests/test_ollama_dynamic_leasing.py`, and see them fail with `uv run devops ci test tests/test_ollama_dynamic_leasing.py`
- [x] 1.2 Add `AI_OLLAMA_SLOT_WAIT` (`devops_cli_ai_ollama_slot_wait_seconds`) to `INSTRUMENTS`, and observe the wait in `acquire_ollama_slot` through `emit`; verify with `uv run devops ci test tests/test_ollama_dynamic_leasing.py tests/test_ai_client_telemetry.py`
- [x] 1.3 Add the Ollama slot wait to the LLM telemetry section of `src/devops_cli/docs/generator.py`, and regenerate the documentation; verify with `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 2. The AI spend dashboard charts the p95 wait by priority

- [x] 2.1 Add `devops_cli_ai_ollama_slot_wait_seconds` p95 by `priority` to the expected quantiles and groups of `test_the_dashboards_chart_latency_errors_reviews_and_findings_devops_cli_sends` in `tests/test_telemetry_instruments.py`, and see it fail with `uv run devops ci test tests/test_telemetry_instruments.py`
- [x] 2.2 Add the panel "Ollama Slot Wait by Priority (p95)" to `k8s/monitoring/dashboards/ai-spend.json`; verify with `uv run devops ci test tests/test_telemetry_instruments.py tests/test_grafana_dashboards.py tests/test_k8s_monitoring_dashboards.py`
- [x] 2.3 Regenerate the documentation; the dashboard changes no command, option or message; verify with `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## Workflow follow-up

- Pending a person: after the merge, Argo CD applies `ai-spend.json`. Run a command that calls Ollama directly, then confirm that the panel "Ollama Slot Wait by Priority (p95)" shows a series for its priority.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
