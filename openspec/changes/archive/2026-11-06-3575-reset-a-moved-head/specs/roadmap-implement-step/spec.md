## MODIFIED Requirements

### Requirement: A step makes the only commit
The first exit check SHALL put `HEAD` back at the commit where the step started, or at the last `wip:` commit of the step, with `git reset --soft` when the agent moved it, so the checkout keeps the work of the agent and the later exit checks judge that work. The step SHALL stop with the class `head_moved` only when the reset exits with a status other than 0.

#### Scenario: A commit by the agent
- **WHEN** the agent commits its work with `git`, and ticks the tasks
- **THEN** the step resets `HEAD` to the commit where it started, prints one muted line that names the moved head and the expected head, and reports done with one commit whose parent is the commit where the step started and that holds the work of the agent

#### Scenario: A commit by the agent after a `wip:` commit
- **WHEN** the step made a `wip:` commit and the agent then makes its own commit in an extra turn
- **THEN** the step resets `HEAD` to the `wip:` commit, and the commit of the step folds the `wip:` commit and the work of the extra turn

#### Scenario: A failed check after the reset
- **WHEN** the agent commits its work and a later exit check fails
- **THEN** the step reports stopped with the reason of that check, not with the class `head_moved`, makes no commit, and the checkout is back at its last `wip:` commit, or at the commit where the step started when it made none

#### Scenario: A reset that fails
- **WHEN** the agent moved `HEAD` and `git reset --soft` to the expected head exits with a status other than 0
- **THEN** the step reports stopped with the class `head_moved`, and the reason names the reset command, its exit status and the output of git
