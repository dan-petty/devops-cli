## ADDED Requirements

### Requirement: A move group names every module of its prefix
The stage plan check SHALL refuse a group that moves a top-level module by name prefix and leaves another module of that prefix for no later group.

#### Scenario: A move group omits a module of its prefix
- **WHEN** The staged tree holds `src/devops_cli/roadmap/stage_ready.py` and `src/devops_cli/roadmap/stage_verify.py`, and one group lists `src/devops_cli/roadmap/stage_ready.py` in `changes` and `src/devops_cli/roadmap/stage/ready.py` in `creates`, with no later group.
- **THEN** `check_proposal` returns a problem that names `src/devops_cli/roadmap/stage_verify.py`.

#### Scenario: A later group moves the missing module
- **WHEN** The staged tree holds `src/devops_cli/roadmap/stage_ready.py` and `src/devops_cli/roadmap/stage_verify.py`, the first group moves `stage_ready.py` into `stage/`, and a later group moves `stage_verify.py` into `stage/`.
- **THEN** `check_proposal` returns no problem for either module.

#### Scenario: A move group leaves a module of another prefix
- **WHEN** The staged tree holds `src/devops_cli/roadmap/stage_ready.py` and `src/devops_cli/roadmap/status.py`, and a group moves `stage_ready.py` into `stage/`.
- **THEN** `check_proposal` returns no problem for `src/devops_cli/roadmap/status.py`.

### Requirement: A move group verifies the whole prefix
The stage plan check SHALL refuse a move group whose `verify` command names one module of the moved prefix instead of the whole prefix.

#### Scenario: A move group verifies one sampled import
- **WHEN** A move group for prefix `stage` gives the verify command `! git grep -n -F devops_cli.roadmap.stage_ready src/ tests/`.
- **THEN** `check_proposal` returns a problem that says the verify command must cover the prefix.

#### Scenario: A move group verifies the prefix
- **WHEN** A move group for prefix `stage` gives the verify command `! git grep -n -F devops_cli.roadmap.stage src/ tests/`.
- **THEN** `check_proposal` returns no problem about the verify command.

### Requirement: The stage prompt asks for every module of a prefix
The stage prompt SHALL tell the planner to list every module of a moved name prefix in the group `changes` and to give a `verify` command that covers the prefix.

#### Scenario: The stage prompt describes a prefix move
- **WHEN** A test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- **THEN** The prompt text tells the planner to name every module of the prefix, not the entry module only, and to verify the prefix.
