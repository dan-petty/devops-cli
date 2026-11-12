## ADDED Requirements

### Requirement: The stage job reads the capabilities that OpenSpec lists
The stage job SHALL read the base capabilities of the checkout from `openspec list --specs --json`, flat as `<name>` or nested as `<area>/<name>`, and SHALL read the purpose and the requirement names of each from its `spec.md`. A spec delta of a reply SHALL name a flat or a nested capability, and the validation SHALL see the base spec of a nested one. With no OpenSpec, the job SHALL know no base capability.

#### Scenario: A nested capability beside a flat one
- **WHEN** the checkout holds `openspec/specs/alpha/spec.md`, `openspec/specs/area/cap-one/spec.md` and an empty folder `openspec/specs/empty`, and OpenSpec lists `alpha` and `area/cap-one`
- **THEN** the base capabilities are `alpha` and `area/cap-one`, each with the requirement names of its file

#### Scenario: No OpenSpec
- **WHEN** the stage job reads the base capabilities with no OpenSpec
- **THEN** it knows no base capability

#### Scenario: A delta of a nested capability
- **WHEN** a reply gives a delta for `roadmap-stage/paths-gate`, and another reply gives a delta for `roadmap-stage/` or `a/../b`
- **THEN** the job accepts the first name and refuses the second reply with the message that names the form of a capability

#### Scenario: The validation of a delta of a nested capability
- **WHEN** the job validates a change with a delta for `area/comment-thread`, and the checkout holds `openspec/specs/area/comment-thread/spec.md`
- **THEN** OpenSpec validates the change in a tree that holds that base spec
