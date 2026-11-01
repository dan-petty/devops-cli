# Tasks

## 1. Remove weight columns and footer from tune report

Reads: none. Changes: `src/devops_cli/commands/ai_gateway.py`.

- [ ] 1.1 Write a test that calls _render_tune_report with a TuneReport whose deployments have no recommended_weight or recommended_concurrency, and asserts the table headers do not contain Weight, Recommended, or Max Parallel, and the footer does not contain litellm_params.weight, and verify that `uv run devops ci test tests/test_ai_gateway.py` fails on the base
- [ ] 1.2 In _render_tune_report, remove Weight, Recommended, and Max Parallel from the headers list. Remove the three corresponding row values (current_weight, recommended_weight, recommended_concurrency). Replace the footer text with a statement that the gateway uses least-busy routing and the measurements are informational. In tune_cmd, update the docstring to say Measure each deployment of a gateway model group and report per-deployment capacity. Remove overrides=settings.ai.gateway_weights and concurrency_overrides=settings.ai.gateway_concurrency from the tune_pool call, and verify that `uv run devops ci test tests/test_ai_gateway.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Remove dead weight functions and fields from gateway_tune

Reads: none. Changes: `src/devops_cli/ai/gateway_tune.py`.

- [ ] 2.1 Write a test that imports gateway_tune and asserts recommend_weights, calculate_hardware_weights, and calculate_hardware_concurrency are not in the module namespace. Assert DeploymentTune has no recommended_weight or recommended_concurrency field. Assert the module docstring contains least-busy and does not contain simple-shuffle, and verify that `uv run devops ci test tests/test_gateway_tune.py` fails on the base
- [ ] 2.2 Update the module docstring to describe least-busy routing. Remove the recommend_weights, calculate_hardware_weights, calculate_hardware_concurrency, _resolve_override, _deployment_backend_map, _is_continuous_engine, and _deployment_hardware_score functions. Remove recommended_weight and recommended_concurrency fields from DeploymentTune. In tune_pool, remove the calls to recommend_weights and calculate_hardware_concurrency, and remove the model_copy update that set those fields. Remove the three function names from __all__. Remove imports of CONST_CONTINUOUS_BATCHING_ENGINES, CONST_DEFAULT_CONTINUOUS_CONCURRENCY, CONST_DEFAULT_SERIAL_CONCURRENCY, CONST_ENGINE_MULTIPLIER_CONTINUOUS_BATCHING, and CONST_ENGINE_MULTIPLIER_SERIAL, and verify that `uv run devops ci test tests/test_gateway_tune.py` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. Remove dead gateway weight settings

Reads: none. Changes: `config/settings.py`.

- [ ] 3.1 Write a test that loads the settings model and asserts the ai section has no gateway_weights field and no gateway_concurrency field, and verify that `uv run devops ci test tests/test_settings.py` fails on the base
- [ ] 3.2 Remove the gateway_weights and gateway_concurrency fields from the ai settings section in config/settings.py, and verify that `uv run devops ci test tests/test_settings.py` passes
- [ ] 3.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 4. Update CLI reference and command docs

Reads: none. Changes: `docs/CLI_REFERENCE.md`, `docs/commands/ai.md`.

- [ ] 4.1 Write a test that reads docs/CLI_REFERENCE.md and docs/commands/ai.md and asserts neither contains the phrase recommend routing weights, and verify that `uv run devops ci test tests/test_docs.py` fails on the base
- [ ] 4.2 In docs/CLI_REFERENCE.md, update the tune command description to say Measure each deployment of a gateway model group and report per-deployment capacity. In docs/commands/ai.md, make the same change to the tune command description, and verify that `uv run devops ci test tests/test_docs.py` passes
- [ ] 4.3 docs/CLI_REFERENCE.md, docs/commands/ai.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
