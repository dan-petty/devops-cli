## ADDED Requirements

### Requirement: The stage job checks each literal of a negative search
The stage job SHALL record the staged hits of each `-e` literal of a negative-search verify command, and check_proposal SHALL apply the rules of the negative search to each literal, the rule of the staged hit and the rule of the created module alike.

#### Scenario: One literal has no staged hit
- **WHEN** A group gives the verify command `! git grep -n -e old_name -e gone_name -- src/ tests/`, and the staged tree holds `old_name` but no `gone_name`.
- **THEN** check_proposal returns one problem that names the literal `gone_name` and says that the search already passes before the change.

#### Scenario: A move group names a module with a second literal
- **WHEN** A move group for prefix `stage` gives the verify command `! git grep -n -e devops_cli.roadmap.stage_ready -e devops_cli.roadmap.stage -- src/ tests/`.
- **THEN** check_proposal returns two problems: the problem of the move and the problem of the created module, and each names the literal `devops_cli.roadmap.stage`.
