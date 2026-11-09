# Design

## Decisions

- **The file wins for one model; the sources merge.** A price that `devops ai cost set-price` saved in the data volume stays in force over the price of the setting for the same model. A setting that won would make `set-price` silently useless for the two reference models. For different models, both sources price. The repository still owns the prices: a new volume holds none, so it takes the prices of the setting.
- **Two dicts in the registry.** `_configured_overrides` holds the setting and `_overrides` holds the file. `_save_overrides` writes only `_overrides`, so `set-price` of another model never copies a price of the setting into the file. If it did, the file would win from then on and the repository would lose its ownership. `_get_override_pricing` and `list_all_pricing` read the merge of both.
- **Settings reach the registry as an argument.** `PricingRegistry(data_dir, settings)`. With no `data_dir`, it loads the settings as it did to find the data directory. With a `data_dir` and no `settings`, it reads no setting. No caller changes, because the callers use `get_pricing_registry()` with no argument.
- **Shape of the value.** A map of model name to `prompt_usd_per_million` and `completion_usd_per_million`, the field names and units of `ModelPricing` and of the file. Each is a finite number of 0 or more. Names are lower-cased, as for the file. The source of such a price is `settings:ai.price_overrides`.
- **Key walk.** `unknown_setting_keys` descends into each value of a mapping field whose values are a model, so a misspelled price field in a ConfigMap is reported. It reads no model name.

## Rejected alternatives

- **The setting wins over the file.** A price set with `set-price` would stop working with no sign.
- **One dict for both sources.** `set-price` would copy the prices of the setting into the file.
- **A path to a second price file.** It needs a file on the volume and keeps the hand step.
- **A ConfigMap key mounted with `subPath` over `pricing_overrides.json`.** It makes `set-price` fail in the pod.
- **Load the settings in every registry.** A test on a temporary `data_dir` would read the settings of the user.
