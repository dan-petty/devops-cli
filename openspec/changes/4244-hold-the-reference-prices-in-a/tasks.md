# Tasks

## 1. Test both reference prices from the committed ConfigMap template

Kind: other. Reads: `k8s/devops/configmap.example.yaml`, `src/devops_cli/ai/spend/pricing.py`, `tests/support/paths.py`, `tests/ai/spend/test_hosted_group_prices.py`, `tests/ai/spend/test_pricing_registry_overrides.py`. Changes: `tests/ai/spend/test_pricing_registry_overrides.py`.

- [ ] 1.1 Add `test_the_template_prices_both_reference_models_with_no_override_file` to `tests/ai/spend/test_pricing_registry_overrides.py`, and import `yaml` and `REPO_ROOT` there. The test reads `k8s/devops/configmap.example.yaml`, loads the document under the `data` key `devops-cli.yaml` as `Settings`, and builds `PricingRegistry` on `tmp_path` with those settings, so the data directory holds no `pricing_overrides.json`. It replaces `_query_genai_prices` with a function that fails the test, then calls `price_reference` for the chat reference model with `kind="chat"` and for the embedding reference model with `kind="embedding"`, each at `settings.ai.reference_provider`. It asserts 0.035 and 1.50 USD per million tokens for `qwen3.8:27b`, 0.01 and 0.0 for `qwen/qwen3-embedding-8b`, the source `settings:ai.price_overrides`, and an empty `caplog.text`. The test fails at the base because no test prices the reference models from the template
  - Verification: `$ uv run devops ci test tests/ai/spend/test_pricing_registry_overrides.py` passes

## Criteria

- Pending person: a setting holds the input and output price per million tokens of a reference model., Delivered by #4242 at the staged commit as `ai.price_overrides`, which stands at `src/devops_cli/config/settings.py:1011:price_overrides: dict[str, AIPriceOverride] = Field(`; only a person records the item as delivered.
- Pending person: PricingRegistry reads the setting before it asks genai-prices., Delivered by #4242 at the staged commit, where the registry merges the setting at `src/devops_cli/ai/spend/pricing.py:709:overrides = {**_HOSTED_GROUP_PRICES, **self._configured_overrides, **self._overrides}` before its genai-prices query; only a person records the item as delivered.
- Pending person: The ConfigMap template sets the prices of qwen3.8:27b (0.035 and 1.50 USD) and qwen/qwen3-embedding-8b (0.01 USD)., Delivered by #4242 at the staged commit at `k8s/devops/configmap.example.yaml:63:price_overrides:`; only a person records the item as delivered.
- Group 1: A test shows that the reports price both models with no pricing_overrides.json file.
- Pending person: The key-walk test of tests/k8s/test_k8s_configmap_keys.py passes., The key-walk test passes at the staged commit and the change adds no settings key, so only a person records the item as delivered.
