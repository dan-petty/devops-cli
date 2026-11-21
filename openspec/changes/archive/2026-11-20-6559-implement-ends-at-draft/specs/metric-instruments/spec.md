## ADDED Requirements

### Requirement: The implement job sends the seconds of its checks and its publish
The implement job SHALL send one sample of `devops_cli_roadmap_step_seconds` with the attributes `repo`, `row` `implement`, `step` and `result` for each call of the scoped checks (`checks`) and for each publish of a branch (`publish`). The `result` SHALL be `error` when the step raised an error, else `ok`.

#### Scenario: A run sends one sample for each step
- **WHEN** a test runs the implement job over a Staged item and over a Planned item with passing checks
- **THEN** the histogram holds one sample for each of `checks` and `publish` with `row` `implement` and `result` `ok`

#### Scenario: Scoped checks that no fix repairs
- **WHEN** a scoped check fails after the last fix round
- **THEN** the histogram holds one `checks` sample with `result` `error`, and no `publish` sample

## REMOVED Requirements

### Requirement: The implement job sends the seconds of its checks, its publish and its watch
**Reason**: The implement Job ends at the draft pull request and watches no check (#6559).
**Migration**: The requirement "The implement job sends the seconds of its checks and its publish" holds the rule.
