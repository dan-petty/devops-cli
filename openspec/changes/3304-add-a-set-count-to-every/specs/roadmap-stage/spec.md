## ADDED Requirements

### Requirement: The stage prompt asks for a count of a claimed set
The stage prompt SHALL ask the plan to give a count of the set that a claim about every member covers, from the `references` tool or from a probe line, and it SHALL ask the proposal rule of `openspec/config.yaml` to hold the same phrase.

#### Scenario: A claim about a set
- **WHEN** the test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the prompt holds `gives a count from a tool of the plan run or from a probe line`

#### Scenario: No tool counts the set
- **WHEN** the test reads the stage prompt
- **THEN** the prompt holds `the count is unverified`, `census command` and `verify` of the first group

#### Scenario: A member has no decision
- **WHEN** the test reads the stage prompt
- **THEN** the prompt holds `removed, restricted, or allowlisted with a reason` and `a member with no decision`

#### Scenario: The count of a claim of no members is above zero
- **WHEN** the test reads the stage prompt
- **THEN** the prompt holds `narrows the claim` and `follow-up issue`

#### Scenario: The issue gives examples of a larger set
- **WHEN** the test reads the stage prompt
- **THEN** the prompt holds `the set that the issue names` and `not the set of its examples`

#### Scenario: The prompt and the config keep one phrase
- **WHEN** the test reads `openspec/config.yaml` and the stage prompt
- **THEN** both files hold `gives a count from a tool of the plan run or from a probe line`

### Requirement: The plan check refuses no word of a requirement text
The plan check SHALL NOT refuse a plan for the word `every`, `all` or `no` in a requirement text, so a claim about a set is judged by its count and never by a word.

#### Scenario: A requirement text holds every
- **WHEN** the test builds a plan whose requirement text holds `every` and whose paths exist at the staged commit
- **THEN** `check_proposal` returns no problem that names the word
