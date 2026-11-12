## ADDED Requirements

### Requirement: A plan that deletes a guard check records it
`check_proposal` SHALL refuse a plan whose work texts delete a test or a `CONST_*` entry when no `weakened_checks` entry names it.

#### Scenario: A plan deletes a guard test and records nothing
- **WHEN** A reply gives a task that deletes `test_all_cli_commands_are_either_exposed_or_excluded`, and `weakened_checks` is empty.
- **THEN** `check_proposal` returns one problem that names `test_all_cli_commands_are_either_exposed_or_excluded`.

#### Scenario: A plan deletes a CONST entry and records nothing
- **WHEN** A reply gives a decision whose reason removes an entry of `CONST_DOCS_INVENTORY`, and `weakened_checks` is empty.
- **THEN** `check_proposal` returns one problem that names `CONST_DOCS_INVENTORY`.

#### Scenario: A plan deletes a guard test and records it
- **WHEN** The reply deletes the same test and gives an entry whose `check` holds `test_all_cli_commands_are_either_exposed_or_excluded`.
- **THEN** `check_proposal` returns no weakened-check problem.

#### Scenario: A plan that deletes no guard check
- **WHEN** A reply deletes no test and no `CONST_*` entry, and `weakened_checks` is empty.
- **THEN** `check_proposal` returns no weakened-check problem.

### Requirement: The proposal file shows each weakened check
`render_change` SHALL write a `## Weakened checks` section that gives the check, what it stopped and the safeguard of each entry, and MUST write no such section for a plan with no entry.

#### Scenario: A plan with one weakened check renders
- **WHEN** A reply gives one `weakened_checks` entry, and `render_change` writes the change.
- **THEN** `proposal.md` holds `## Weakened checks` with the check, what it stopped and the safeguard of the entry, after `## Impact` and before `## Feasibility`.

#### Scenario: A plan with no weakened check renders
- **WHEN** A reply gives no `weakened_checks` entry, and `render_change` writes the change.
- **THEN** `proposal.md` holds no `## Weakened checks` section.
