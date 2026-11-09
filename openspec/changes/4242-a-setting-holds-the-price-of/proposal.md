# Proposal

## Why

The prices of the reference models `qwen3.8:27b` and `qwen/qwen3-embedding-8b` live only in the hand-set file `pricing_overrides.json` in the data volume of the Service. The repository does not own them. A new volume, workstation or cluster has no price, so `PricingRegistry.price_reference` logs an unpriced warning and the savings in `devops ai cost` show as not priced (#4242).

## What Changes

- Add the setting `ai.price_overrides` to `src/devops_cli/config/settings.py`: a map of model name to the model `AIPriceOverride` (`prompt_usd_per_million` and `completion_usd_per_million`, each a finite number of 0 or more). The default is an empty map.
- Make `PricingRegistry` in `src/devops_cli/ai/spend/pricing.py` take an optional `settings` argument. It reads `ai.price_overrides` from it, or from the loaded settings when it has no `data_dir`. A registry on a `data_dir` with no `settings` reads no setting, so a test on a temporary directory is not affected by the settings of the user.
- Precedence: the registry keeps the prices of the setting apart from the prices of the file. For one model, the file `pricing_overrides.json` wins. The two sources merge for different models. `devops ai cost set-price` saves only the file prices, so it never copies a price of the setting into the file, and `remove-price` of a hand price gives back the price of the setting.
- Make the key walk `unknown_setting_keys` in `src/devops_cli/config/setting_keys.py` check the fields of each value of a mapping field whose values are a model. It still reads no model name.
- Set both prices in `k8s/devops/configmap.example.yaml`, with a comment.
- Regenerate `docs/CONFIGURATION.md` and `README.md` with `devops docs generate --sync-readme`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-spend-pricing`: A price override can come from the setting `ai.price_overrides`, and the file wins for one model
- `roadmap-service-deployment`: The ConfigMap template also holds the two prices

## Impact

- Code: `src/devops_cli/config/settings.py`, `src/devops_cli/ai/spend/pricing.py`, `src/devops_cli/config/setting_keys.py`
- Config: `k8s/devops/configmap.example.yaml`
- Documents: `docs/CONFIGURATION.md`, `README.md`
- Tests: `tests/ai/spend/test_pricing_registry_overrides.py` (new), `tests/k8s/test_k8s_configmap_keys.py`
- Deploy order: the section `ai` refuses a key that it does not declare (`extra="forbid"`). A ConfigMap that holds `ai.price_overrides` stops an image that is older than this change. The live ConfigMap needs the key at the same time as the new image or after it. An image of this change loads a ConfigMap with no key (the default is an empty map).

## Feasibility

- `uv run python` with genai-prices 0.1.13: `genai_prices.calc_price(Usage(input_tokens=1000, output_tokens=1000), "qwen3.8:27b", provider_id="openai")` and the same call for `qwen/qwen3-embedding-8b` raise `LookupError: Unable to find model with model_ref=...`. So genai-prices does not know both names, and no library covers the price.
- `src/devops_cli/ai/spend/pricing.py` reads the file only in `_load_persisted_overrides`, and `_get_override_pricing` and `list_all_pricing` read `self._overrides`. `_save_overrides` writes all of `self._overrides`, so a price of the setting in the same dict would be copied into the file by the next `set-price`. The change keeps a second dict for the setting to avoid this.
- `AIConfig` has `extra="forbid"`, and `Settings` has `extra="ignore"` (`src/devops_cli/config/settings.py`), so the new key must be a declared field of `AIConfig`.
- The key walk `unknown_setting_keys` read the value type of a mapping field as a nested model and reported the model names. The test `test_a_key_of_a_price_in_a_copy_of_the_example_is_checked_and_a_model_name_is_not` covers the fix.

## Existing Tool Considered

genai-prices 0.1.13 has no setting for a price of its own. `devops ai cost update-pricing --source <file>` needs a hand step and a file on the volume. A ConfigMap key mounted with `subPath` over `pricing_overrides.json` needs no code, but it makes `devops ai cost set-price` fail in the pod. The change builds a small setting and a registry read on top of the existing override path. The cost is about 80,000 tokens to build and review, and 5 to 10 minutes of CI under the shared lock. Keeping it costs nothing.
