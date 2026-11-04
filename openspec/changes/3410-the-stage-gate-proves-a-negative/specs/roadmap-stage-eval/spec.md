## ADDED Requirements

### Requirement: The replay reads the search evidence from its case
The stage eval replay MUST read the negative-search evidence from the `search_evidence` mapping of its case and MUST run no git command.

#### Scenario: The replay judges a negative search
- **WHEN** The stage eval replay judges a plan with a negative-search verify command.
- **THEN** The replay reads the evidence from the case and runs no git grep.

### Requirement: The golden set holds the case of a refused and a kept negative search
The stage eval case MUST hold the move plan of the stage modules with its recorded search evidence and MUST assert the no-hit refusal, the refusal of the bare prefix `devops_cli.roadmap.stage`, and the acceptance of the dotted prefix `devops_cli.roadmap.stage_`.

#### Scenario: The replay runs the case of the moved modules
- **WHEN** The stage eval replay runs the case of the move of the stage modules.
- **THEN** The replay reports the two refusals and the acceptance for the dotted prefix `devops_cli.roadmap.stage_`.
