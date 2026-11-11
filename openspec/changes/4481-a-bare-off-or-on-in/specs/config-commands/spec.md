## ADDED Requirements

### Requirement: A mode setting reads a bare YAML 1.1 off or on
The settings loader SHALL read a bare YAML 1.1 `off` as the mode `off` and a bare `on` as the mode `on` for `roadmap.intake.jev` and for each mode of `roadmap.decisions`, and a mode that `devops config set` writes SHALL load as the same mode.

#### Scenario: Bare off in the intake config
- **WHEN** The config file holds `roadmap.intake.jev: off`.
- **THEN** `RoadmapIntakeConfig` loads with `jev` equal to `off`.

#### Scenario: Bare on in the intake config
- **WHEN** The config file holds `roadmap.intake.jev: on`.
- **THEN** `RoadmapIntakeConfig` loads with `jev` equal to `on`.

#### Scenario: A decision mode reads the YAML booleans
- **WHEN** `TypeAdapter(DecisionMode)` validates `False` and `True`.
- **THEN** The adapter returns `off` for `False` and `on` for `True`.

#### Scenario: A written mode reloads
- **WHEN** `devops config set roadmap.intake.jev off` writes the file and the settings load.
- **THEN** The loaded `jev` equals `off`.
