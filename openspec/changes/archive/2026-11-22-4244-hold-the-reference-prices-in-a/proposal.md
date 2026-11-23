# Proposal

## Why

#4244 asks that the repository own the price of the two reference models, so a new data volume needs no hand-written price file. #4242 already merged that code: the setting, the registry read and the template prices stand at the staged commit. One acceptance criterion still has no test, that the reports price both models from the committed template with no price file.

## What Changes

- Add `test_the_setting_prices_both_reference_models_with_no_override_file` to `tests/ai/spend/test_pricing_registry_overrides.py`: it constructs settings with `ai.price_overrides` for both reference models, and prices both reference models through the call the reports make, on an empty data directory and with the genai-prices query replaced by a stub that fails the test.
- The AI section of the settings already holds the price of a model, and the registry merges it before the genai-prices query, so the change adds no code.
- The ConfigMap template already names both reference models and holds their three prices, so the change sets no manifest value.
- No spec delta: the change touches only `tests/ai/spend/test_pricing_registry_overrides.py`, and the behavior it checks is already held by the capabilities `ai-spend-pricing` and `roadmap-service-deployment`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: `tests/ai/spend/test_pricing_registry_overrides.py`

## Feasibility

- The issue asks for code that the staged tree already holds. The probe `The path `pricing_overrides.json` is no file of the staging commit. No commit in the history deleted or renamed it.` shows the hand-set file is no repository file, and `read_issue 4242` answers `#4242 issue, closed (completed): feat(ai): a setting holds the price of a reference model` with the comment `Released in v0.103.0`.
- The probe `The path `tests/k8s/test_k8s_configmap_keys.py` is a file of the staging commit.` confirms the key-walk test of the issue, and `tests/k8s/test_k8s_configmap_keys.py:61:config["ai"]["price_overrides"] = {"example-model": {"prompt_usd_per_milion": 1.0}}` shows that the walk checks the fields of a price and takes a model name as a key of the user.
- The setting is staged: `src/devops_cli/config/settings.py:948:class AIPriceOverride(BaseModel):` holds the prompt, the completion and the cache-read price, and `src/devops_cli/config/settings.py:1011:price_overrides: dict[str, AIPriceOverride] = Field(` declares the map from model name to that price.
- The registry reads the setting before genai-prices: `src/devops_cli/ai/spend/pricing.py:620:source="settings:ai.price_overrides",` names the source, `src/devops_cli/ai/spend/pricing.py:709:overrides = {**_HOSTED_GROUP_PRICES, **self._configured_overrides, **self._overrides}` merges the file over the setting over the built-in price, and the genai-prices query follows at `src/devops_cli/ai/spend/pricing.py:751:resolved = _query_genai_prices(`.
- The template holds the prices of the issue: `k8s/devops/configmap.example.yaml:61:reference_model: qwen3.8:27b`, `k8s/devops/configmap.example.yaml:62:reference_embedding_model: qwen/qwen3-embedding-8b`, `k8s/devops/configmap.example.yaml:63:price_overrides:`, `k8s/devops/configmap.example.yaml:65:prompt_usd_per_million: 0.035`, `k8s/devops/configmap.example.yaml:66:completion_usd_per_million: 1.50`, `k8s/devops/configmap.example.yaml:68:prompt_usd_per_million: 0.01` and `k8s/devops/configmap.example.yaml:69:completion_usd_per_million: 0.0`.
- `read_spec ai-spend-pricing` answers the requirement `The setting ai.price_overrides prices a model` with the scenario `Empty data directory`, and `read_spec roadmap-service-deployment` answers `The ConfigMap template holds the prices of the reference models` with the scenario `The rendered template is read for prices`, so the behavior of the new test is already specified and the change carries no spec delta.
- No test prices both reference models from settings with an empty data directory today: `tests/ai/spend/test_pricing_registry_overrides.py:59:def test_a_setting_prices_a_model_with_an_empty_data_directory(` prices one model from settings that the test builds, and `references pricing_overrides.json` lists no other test module of the spend reports.
- The test constructs its settings in memory, so its one precondition is Python: it needs no client of a service, no network, and reads no committed config file.
- The constants that the test relies on are staged: `tests/ai/spend/test_pricing_registry_overrides.py:23:CHAT_MODEL = "qwen3.8:27b"`, `tests/ai/spend/test_pricing_registry_overrides.py:24:EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"`, `src/devops_cli/config/defaults.py:110:DEFAULT_AI_REFERENCE_PROVIDER: str = "openai"`, the provider that the template leaves at its default, and `src/devops_cli/config/defaults.py:468:DEFAULT_AI_PRICING_OVERRIDES_FILENAME: str = "pricing_overrides.json"`, the file that the empty data directory does not hold.
- The reports make the call that the test asserts: `src/devops_cli/ai/spend/ledger.py:311:chat=registry.price_reference(` prices the chat reference model, and `src/devops_cli/ai/spend/ledger.py:314:embedding=registry.price_reference(` prices the embedding one.
- The first checks against the real system are `uv run devops ci test tests/ai/spend/test_pricing_registry_overrides.py`, which must pass with the new test, and `uv run devops ci --check --only k8s`, which must accept the template. Both run programs of the runner image, `uv` and `pytest` for the first and `kubectl` for the second, so no program of the plan is NOT_IN_RUNNER and the only failure class that the plan needs is a failed assertion.
- The pod settings of the runner hold: the test writes only under the temporary directory that pytest gives it, so `readOnlyRootFilesystem: true` holds, and it runs as the user of the job, so `runAsNonRoot: true` holds.
- The plan adds no setting, no registry branch and no ConfigMap key, because the issue asks to create code that the staged tree already holds.

## Existing Tool Considered

genai-prices 0.1.13 stays the pricing library of the repository: it is open and maintained, and it holds no price for qwen3.8:27b or qwen/qwen3-embedding-8b, which the setting ai.price_overrides already supplies. The change builds no code, so it adds no build, upkeep or fix cost.

## Dependencies

None.
