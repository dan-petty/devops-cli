## ADDED Requirements

### Requirement: The setting ai.price_overrides prices a model
The AI configuration SHALL hold the setting `ai.price_overrides`, a map of model name to a prompt price and a completion price in USD per million tokens, each a finite number of 0 or more. The default SHALL be an empty map. The pricing registry SHALL price a model from this setting when `pricing_overrides.json` in the data directory holds no price for it.

#### Scenario: Empty data directory
- **WHEN** `ai.price_overrides` holds 0.035 USD prompt and 1.50 USD completion for `qwen3.8:27b`, and the data directory holds no `pricing_overrides.json`
- **THEN** the price of `qwen3.8:27b` is 0.035 USD prompt and 1.50 USD completion per million tokens, and the registry logs no unpriced warning.

#### Scenario: A negative price
- **WHEN** `ai.price_overrides` holds a price below 0
- **THEN** the settings refuse it when they load.

### Requirement: The file on the volume wins over the setting for one model
When `pricing_overrides.json` and `ai.price_overrides` both price the same model, the registry MUST use the price of the file. For different models, the registry SHALL use both sources.

#### Scenario: Both sources price one model
- **WHEN** the file holds 9.0 USD prompt for `qwen3.8:27b` and the setting holds 0.035 USD
- **THEN** the price of `qwen3.8:27b` is 9.0 USD prompt.

#### Scenario: The sources price different models
- **WHEN** the setting prices `qwen3.8:27b` and the file prices `other-model`
- **THEN** the registry prices both models.

### Requirement: set-price never copies a price of the setting into the file
`devops ai cost set-price` SHALL save only the prices that a person set. It MUST NOT write a price of `ai.price_overrides` into `pricing_overrides.json`.

#### Scenario: A price for another model
- **WHEN** a person sets a price for `other-model` and the setting prices `qwen3.8:27b`
- **THEN** `pricing_overrides.json` holds `other-model` only.

#### Scenario: A hand price is removed
- **WHEN** a person sets a hand price for `qwen3.8:27b` and then removes it
- **THEN** the price of `qwen3.8:27b` is the price of the setting again.
