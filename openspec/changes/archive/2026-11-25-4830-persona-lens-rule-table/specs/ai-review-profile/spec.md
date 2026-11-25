## ADDED Requirements

### Requirement: Review profile records lens and rule id

`ReviewProfile` SHALL include `lens` (default `"none"`) and `lens_rule` (default `""`) beside `prompt_digest`, and `record_lens_choice` / `ReviewProfiler` SHALL record the chosen lens, rule id, and `ai.lens` / `ai.lens.rule` span attributes.

#### Scenario: Profile records selected lens or none

- **WHEN** a review profile builds with a selected `devsecops` lens choice vs no lens choice
- **THEN** the serialized `profile.json` holds `lens="devsecops"` with `lens_rule` in the first case, and `lens="none"`, `lens_rule=""` in the second, alongside `prompt_digest`
