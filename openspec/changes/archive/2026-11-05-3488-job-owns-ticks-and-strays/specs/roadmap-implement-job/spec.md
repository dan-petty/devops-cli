## REMOVED Requirements

### Requirement: A stop site passes a typed class
**Reason**: The step ticks every task of a passing group, so it never ends with an unticked task and passes no class `not_ticked`.
**Migration**: The requirement "A stop site passes a typed class of its cause" holds the rule of the other stops.

## ADDED Requirements

### Requirement: A stop site passes a typed class of its cause
Each stop of the job whose cause has a class SHALL pass that class, and the stop comment and `implement.failure` SHALL hold it. The classifier SHALL NOT decide a class that a site passes. The words of the last message of the agent and the words of a task SHALL NOT change a class. A step that changed no file SHALL pass `no_change_in_fix` in a fix step and `plan_defect` in a group step.

#### Scenario: A fix step that changed no file
- **WHEN** a fix step stops with the reason "The agent changed no file." and its last message says "The item is already implemented."
- **THEN** the comment holds the class `no_change_in_fix` and `implement.failure` is `no_change_in_fix`

#### Scenario: A group step that changed no file
- **WHEN** the step of group 2 stops with the reason "The agent changed no file."
- **THEN** the class is `plan_defect`

#### Scenario: A lost test, a moved HEAD and the output cap
- **WHEN** a step stops because the agent removed a test, moved HEAD, or reached the output cap
- **THEN** the classes are `tests_lost`, `head_moved` and `output_cap`

#### Scenario: The tier decision
- **WHEN** a turn ends with an error whose text the classifier reads as `parser`, and a second turn ends with the output cap and a message that holds the words of a parser failure
- **THEN** the step moves to the next tier after the first turn only, and the outcome of the step holds the class `parser` for the first and `output_cap` for the second, the class that the decision read
