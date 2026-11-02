# roadmap-job-limits Specification

## Purpose
The roadmap jobs carry numeric limits that can cut work short. Each limit has a class and a reason, so a new limit is a decision that a person sees, and the raised limits fit the context windows and the comment sizes of the stack.

## Requirements

### Requirement: Every numeric limit of the roadmap jobs has a class
Each numeric value named `CONST_ROADMAP_*` in `config/constants.py` or `DEFAULT_ROADMAP_*` in `config/defaults.py` SHALL have one entry in the table of `tests/roadmap/test_roadmap_limit_classes.py`, with a class and a reason. The classes are `raised`, `guard`, `window`, `setting`, `kept` and `other`. A limit that left the code SHALL be in the list of removed names, and none of them SHALL be defined again.

#### Scenario: A limit with no class
- **WHEN** a numeric `CONST_ROADMAP_*` value is added and the table has no entry for it
- **THEN** the test fails and names the limit

#### Scenario: An entry for a limit that is gone
- **WHEN** the table names a limit that no module defines
- **THEN** the test fails and names the entry

#### Scenario: A removed limit comes back
- **WHEN** a module defines `CONST_ROADMAP_STAGE_MAX_OUTPUT_TOKENS`
- **THEN** the test fails

### Requirement: The raised limits fit the windows of the stack
The default step budget and the turn reserve SHALL fit the default context window of the implement task. The output cap of a reply, the packed file and the tool result of a step SHALL fit that window too. The body that the alternatives check sends SHALL be at most a quarter of the planner window that the example ConfigMap sets.

#### Scenario: The step budget and the reserve
- **WHEN** the default step budget and the turn reserve are added
- **THEN** the sum is not above the default window of the implement task

#### Scenario: The alternatives body
- **WHEN** the example ConfigMap sets the window of the `analysis` task
- **THEN** the body cap of the alternatives check is at most a quarter of that window

#### Scenario: The output cap and the inputs
- **WHEN** the output cap of a reply and the default step budget are added
- **THEN** the sum is not above the default window of the implement task

### Requirement: The caps of the stack agree with each other
A reply at the output cap, at the measured rate of the model, with a cold read of the window, SHALL end before the default deadline of a model call. The lines of the map SHALL fit one tool answer. The texts of a stop report SHALL fit one comment of 65536 characters.

#### Scenario: The deadline of a call
- **WHEN** a reply at the output cap is made at 38 tokens per second after a cold read of 90 seconds
- **THEN** it ends before the default call deadline

#### Scenario: A stop report
- **WHEN** the diff, the reason and the last message of an agent are at their caps
- **THEN** together they are shorter than one comment of 65536 characters

#### Scenario: The lines of the map
- **WHEN** the map holds its most files at their longest line
- **THEN** the lines are not longer than one tool answer
