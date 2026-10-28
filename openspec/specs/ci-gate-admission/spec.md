# ci-gate-admission Specification

## Purpose
How `devops ci` limits the CPU-heavy gates that run at the same time on one host, so that agents in sibling worktrees take turns and each gate runs with the CPU it needs.

## Requirements

### Requirement: A gate with a heavy check waits for a free slot
A run of `devops ci` that selects the `test`, `security` or `typecheck` check SHALL take one gate slot before it starts any check, and SHALL give the slot back when it ends. While every slot is held, the run SHALL wait and start a check only after a slot is free. All worktrees of one repository SHALL share the same slots.

#### Scenario: The run waits while every slot is held
- **WHEN** the number of slots is 1, a slot is held by another process, and `devops ci --only test` starts in a sibling worktree
- **THEN** the run starts no check while the slot is held
- **AND** the run starts its checks after the other process gives the slot back

#### Scenario: The run gives the slot back
- **WHEN** a run that holds a slot ends, whether its checks pass or fail
- **THEN** the next run that waits takes that slot

### Requirement: A gate with only light checks takes no slot
A run of `devops ci` that selects none of the heavy checks SHALL start at once, also when every slot is held.

#### Scenario: The pre-push selection never waits
- **WHEN** every slot is held and `devops ci --check --only lint,format,actionlint,zizmor` starts
- **THEN** the run starts its checks at once and takes no slot

### Requirement: The full-suite commands take a slot
`devops ci coverage`, and `devops ci test` run with no path and no `-n` option, SHALL take a gate slot before they start pytest, because pytest then starts one worker for each CPU. A `devops ci test` run narrowed by paths or by `-n` SHALL start at once and take no slot.

#### Scenario: The full suite waits for a slot
- **WHEN** every slot is held and `devops ci test` starts with no path
- **THEN** the command does not start pytest until a slot is free

#### Scenario: Coverage waits for a slot
- **WHEN** every slot is held and `devops ci coverage` starts
- **THEN** the command does not start pytest until a slot is free

#### Scenario: A narrowed run never waits
- **WHEN** every slot is held and `devops ci test tests/test_x.py` starts
- **THEN** the command starts pytest at once and takes no slot

### Requirement: A dry run and a cached verdict take no slot
A dry run SHALL make no slot request and SHALL not wait. A run that answers from a cached passing verdict SHALL take no slot.

#### Scenario: A dry run with every slot held
- **WHEN** every slot is held and `devops ci --dry-run` runs
- **THEN** the run prints its plan at once and creates no slot file

#### Scenario: A cached verdict with every slot held
- **WHEN** every slot is held and the cache holds a passing verdict for the unchanged tree
- **THEN** the run reports the cached verdict at once

### Requirement: A slot ends with its holder
A slot SHALL be free when the process that holds it has ended, whether the process exits, raises or is killed with SIGKILL.

#### Scenario: A killed holder
- **WHEN** a process that holds the only slot is killed with SIGKILL
- **THEN** a run that waits for a slot takes it without any other action

### Requirement: A stop signal ends the wait
A stop signal that reaches a run while it waits for a slot SHALL end the run at once, without starting a check and without holding a slot.

#### Scenario: Ctrl-C while the run waits
- **WHEN** a run waits because every slot is held, and Ctrl-C comes
- **THEN** the run ends without a check started
- **AND** the run holds no slot, so a later run can take one when the others are free

### Requirement: A waiting run names the holders
While a run waits, it SHALL say once that it waits, how many slots there are, and, for each held slot, the process number and the worktree of its holder.

#### Scenario: The wait message
- **WHEN** a run waits and the holder of the only slot is process 4321 in a worktree named `w-1111`
- **THEN** the output names the number of slots, process 4321 and the worktree `w-1111`

### Requirement: The number of slots is set by the setting or the CPU count
The number of slots SHALL be the value of `ci.gate_slots` when it is set. Otherwise it SHALL be the CPU count of the process divided by 16 and rounded down, with a minimum of 1. A value below 1 SHALL be refused with an error that names the setting.

#### Scenario: The default on a host with 4 CPUs
- **WHEN** `ci.gate_slots` is not set and the process has 4 CPUs
- **THEN** the number of slots is 1

#### Scenario: The default on a host with 16 CPUs
- **WHEN** `ci.gate_slots` is not set and the process has 16 CPUs
- **THEN** the number of slots is 1

#### Scenario: The default on a host with 32 CPUs
- **WHEN** `ci.gate_slots` is not set and the process has 32 CPUs
- **THEN** the number of slots is 2

#### Scenario: A value below 1
- **WHEN** `ci.gate_slots` is 0
- **THEN** the command exits with an error that names `ci.gate_slots`

### Requirement: The wait is not gate time
The time a run waits for a slot SHALL NOT count in the elapsed time of the gate, in its summary or in its over-budget warning. The run SHALL record the wait as one observation of the histogram `devops_cli_ci_gate_slot_wait_seconds`.

#### Scenario: A long wait and a fast gate
- **WHEN** a run waits 600 s for a slot and then runs checks that take 30 s
- **THEN** the summary reports an elapsed time of about 30 s and no over-budget warning
- **AND** the histogram `devops_cli_ci_gate_slot_wait_seconds` has one observation of about 600
