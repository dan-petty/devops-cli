## ADDED Requirements

### Requirement: A direct pytest run with automatic workers takes a slot
A pytest run that takes its worker count from `-n logical` or `-n auto`, and that no holder of a slot started, SHALL take a gate slot before it starts its workers, and SHALL wait while every slot is held. It SHALL start at most the CPU count of the process divided by the number of slots, and at least one worker.

#### Scenario: A gate holds the only slot
- **WHEN** the number of slots is 1, a gate in another process holds the slot, and a direct pytest run asks for 16 workers on 16 CPUs
- **THEN** the run waits and names the holder
- **AND** the run starts 16 workers after the gate gives the slot back

#### Scenario: Two slots on 32 CPUs
- **WHEN** `ci.gate_slots` is not set, the process has 32 CPUs, and xdist asks for 32 workers
- **THEN** the run starts 16 workers

### Requirement: A run that a slot holder started takes no second slot
While a process holds a gate slot, its environment, which its children get, SHALL hold `DEVOPS_CLI_GATE_SLOT_HELD=1`. A pytest run that finds this variable SHALL take no slot and SHALL keep the worker count of xdist.

#### Scenario: The pytest of a gate
- **WHEN** a gate holds the only slot and its pytest asks for 32 workers
- **THEN** the pytest run starts 32 workers at once and does not wait

#### Scenario: The mark ends with the slot
- **WHEN** a process gives its slot back
- **THEN** `DEVOPS_CLI_GATE_SLOT_HELD` is not in its environment
