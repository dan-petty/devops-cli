## ADDED Requirements

### Requirement: The job makes the scratch directory before the first step
The implement job SHALL create `.data/agent/scratch/` in the checkout before the first model request of a step.

#### Scenario: A fresh checkout
- **WHEN** the job starts an item in a checkout that holds no `.data/agent/scratch/`
- **THEN** the directory exists before the first request and `git check-ignore` reports it ignored

### Requirement: The prompt names create_directory for a new directory
The prompt of the implement step SHALL name `create_directory` for a new directory and SHALL hold no `python -c` command that calls `mkdir`.

#### Scenario: The rendered prompt
- **WHEN** the prompt of the step is rendered
- **THEN** the text names `create_directory` and holds no `python -c` command that calls `mkdir`
