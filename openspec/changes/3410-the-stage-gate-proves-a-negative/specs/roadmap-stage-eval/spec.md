## ADDED Requirements

### Requirement: The replay reads the search evidence from its case
The stage eval replay MUST read the negative-search evidence from its case and MUST run no git command.

#### Scenario: The replay judges a negative search
- **WHEN** The stage eval replay judges a plan with a negative-search verify command.
- **THEN** The replay reads the evidence from the case and runs no git grep.

### Requirement: The golden set holds the case of a kept negative search
The stage eval case MUST hold the plan of #3378 with its recorded search evidence and MUST assert the no-hit refusal, the created-module refusal and the acceptance of the whole module prefix of the moved modules.

#### Scenario: The replay runs the case of the moved modules
- **WHEN** The stage eval replay runs the case that holds the plan of #3378.
- **THEN** The replay reports the two refusals and the acceptance for the whole module prefix of the moved modules.
