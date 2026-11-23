# Design

## Decisions

- **Hold the price of a model in one mapping in the AI section of the settings, keyed by model name, rather than in a field for each reference model.**: A mapping follows the model when a reference model changes, and the mapping stands at `src/devops_cli/config/settings.py:1011:price_overrides: dict[str, AIPriceOverride] = Field(`.
- **Resolve the price in the order override file, then setting, then genai-prices.**: The registry merges the three at `src/devops_cli/ai/spend/pricing.py:709:overrides = {**_HOSTED_GROUP_PRICES, **self._configured_overrides, **self._overrides}`, so a price that a person saved on the volume keeps its effect and the repository default survives a new volume.
- **Add the one test that the criteria still lack, in `tests/ai/spend/test_pricing_registry_overrides.py`, and change no code.**: The setting, the registry order and the template prices stand at the staged commit, as `src/devops_cli/config/settings.py:1011:price_overrides: dict[str, AIPriceOverride] = Field(` and `k8s/devops/configmap.example.yaml:63:price_overrides:` show, so code that adds them again would duplicate delivered behavior.
- **Construct the settings directly in the test instead of reading the committed template.**: `docs/TESTING.md` and the `test-tree` row (`check_no_new_test_reads_a_committed_manifest_or_config_file`) refuse new tests that read committed config files. Unit tests check source code with inputs that they construct.
- **Price through the call that the reports make, with the genai-prices query replaced by a stub that fails the test, and assert no unpriced warning.**: The reports price the chat model at `src/devops_cli/ai/spend/ledger.py:311:chat=registry.price_reference(`, so the test takes the same path and proves that the setting answers before the library is asked.
- **Build the registry on a temporary data directory with settings that price both reference models.**: The criterion is that no price file is needed, and the registry reads that file only when `src/devops_cli/ai/spend/pricing.py:602:self.overrides_path = self.ai_dir / DEFAULT_AI_PRICING_OVERRIDES_FILENAME` exists.

## Rejected alternatives

- **A second JSON file in the repository for the prices.**: The setting is a declared key of the AI section at `src/devops_cli/config/settings.py:1011:price_overrides: dict[str, AIPriceOverride] = Field(`, and the ConfigMap carries it to the pod; a second file adds a format that a new volume also loses.
- **A field in the AI section for each of the two reference models.**: The mapping keyed by model name stands at `src/devops_cli/config/settings.py:1011:price_overrides: dict[str, AIPriceOverride] = Field(`, so a change of reference model needs no new field.
- **The setting wins over the override file.**: The file is merged last at `src/devops_cli/ai/spend/pricing.py:709:overrides = {**_HOSTED_GROUP_PRICES, **self._configured_overrides, **self._overrides}`, so a price that a person saved on the volume keeps its effect.
- **Add the setting and the registry branch again for this issue.**: #4242 delivered them at the staged commit: `src/devops_cli/config/settings.py:1011:price_overrides: dict[str, AIPriceOverride] = Field(`, `src/devops_cli/ai/spend/pricing.py:709:overrides = {**_HOSTED_GROUP_PRICES, **self._configured_overrides, **self._overrides}` and `k8s/devops/configmap.example.yaml:63:price_overrides:`. That change is archived as `openspec/changes/archive/2026-11-09-4242-a-setting-holds-the-price-of`.
- **Put the new test in `tests/k8s/test_k8s_configmap_keys.py`.**: That module walks a settings mapping that the test builds and imports no pricing registry, so the pricing assertion belongs in `tests/ai/spend/test_pricing_registry_overrides.py`, which already prices a model with an empty data directory at `tests/ai/spend/test_pricing_registry_overrides.py:59:def test_a_setting_prices_a_model_with_an_empty_data_directory(`.

## Security

The new test constructs its settings in memory and opens no cluster, no client and no network, so nothing crosses a trust boundary. `uv run devops ci test tests/ai/spend/test_pricing_registry_overrides.py` verifies that the setting prices both reference models without querying genai-prices or reading a price file.
