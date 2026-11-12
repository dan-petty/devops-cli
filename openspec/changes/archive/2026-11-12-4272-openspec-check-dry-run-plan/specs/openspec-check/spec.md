## Purpose

`devops openspec check` runs the OpenSpec gate over a checkout and reports each problem that it finds. In a dry run it lists the `openspec` commands of the gate and runs none of them.

## ADDED Requirements

### Requirement: Dry run lists the gate commands

In a dry run, `devops openspec check` SHALL start no process and read no output of a planned process. It SHALL print the `openspec` commands of the gate in the order that the gate runs them, each with the variables that the run sets, and a scratch directory as a named placeholder. It SHALL name the command that runs once for each active change. It SHALL then say that it would run the gate, and exit 0.

#### Scenario: check_in_dry_run_lists_the_commands

- **WHEN** `devops openspec check` runs with `DEVOPS_CLI_DRY_RUN=1` on a tree with no change and no spec
- **THEN** the exit code is 0, the output lists the planned `openspec` commands and then says that the gate would run, the output holds no `not JSON` text, and the process runner starts no process

#### Scenario: the_plan_is_the_commands_the_gate_runs

- **WHEN** the plan is compared with the commands that the gate runs over a tree with no change and no spec
- **THEN** the plan lists the same commands in the same order, and then the `show` command that runs once for each active change
