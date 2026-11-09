# Tasks

## 1. Price a model from the setting

Reads: `src/devops_cli/config/settings.py`, `src/devops_cli/ai/spend/pricing.py`, `src/devops_cli/config/setting_keys.py`, `tests/ai/spend/test_ai_spend_pricing.py`. Changes: `tests/ai/spend/test_pricing_registry_overrides.py` (new), `tests/k8s/test_k8s_configmap_keys.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/ai/spend/pricing.py`, `src/devops_cli/config/setting_keys.py`.

- [x] 1.1 Add `tests/ai/spend/test_pricing_registry_overrides.py` and a key-walk test in `tests/k8s/test_k8s_configmap_keys.py`. Run them and see them fail
  - Verification: `$ uv run devops ci test tests/ai/spend/test_pricing_registry_overrides.py` fails on the base
- [x] 1.2 Add `AIPriceOverride` and `AIConfig.price_overrides` to `settings.py`. Give `PricingRegistry` the `settings` argument and the `_configured_overrides` dict. Make `unknown_setting_keys` walk the values of a mapping of models
  - Verification: `$ uv run devops ci test tests/ai/spend/test_pricing_registry_overrides.py tests/ai/spend/test_ai_spend_pricing.py tests/k8s/test_k8s_configmap_keys.py` passes

## 2. The template owns the prices

Reads: `k8s/devops/configmap.example.yaml`. Changes: `k8s/devops/configmap.example.yaml`.

- [x] 2.1 Set `ai.price_overrides` for `qwen3.8:27b` (0.035 and 1.50) and `qwen/qwen3-embedding-8b` (0.01 and 0), and update the comment
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_configmap_keys.py tests/k8s/test_k8s_configmap.py` passes

## 3. Regenerate the documents

Reads: `docs/CONFIGURATION.md`, `README.md`. Changes: `docs/CONFIGURATION.md`, `README.md`.

- [x] 3.1 Run `uv run devops docs generate --sync-readme`
  - Verification: `$ uv run devops docs generate --sync-readme` leaves no further diff
