## ADDED Requirements

### Requirement: The probe lists the test cases of a cited test module
The premise probe SHALL list, for each test module and each source file that the issue cites and that the staging commit holds, the test cases of the module whose body names a symbol, message or constant that the source file binds at module level.

#### Scenario: A case names a symbol of the cited source file
- **WHEN** The issue cites `tests/roadmap/stage/test_roadmap_stage_probe.py` and `src/devops_cli/roadmap/stage/stage_probe.py`, and the test module holds a case that calls `blocked_by`.
- **THEN** The probe text names that case in the line of the two files, and names no case of the module that calls none of the names of the source file.

#### Scenario: No case names the cited source file
- **WHEN** No case of the cited test module names a name that the cited source file binds.
- **THEN** The probe text states that the test module holds no case that names the source file.

### Requirement: The probe names the pair that its command bound leaves unlisted
The premise probe SHALL name each test module and source file whose cases its command bound leaves unlisted, in the line that reports the reached bound.

#### Scenario: The bound is reached before a pair is listed
- **WHEN** The cited paths use all ten commands of the probe before the listing of a test module and a source file.
- **THEN** The line that reports the reached bound names that test module and that source file.

### Requirement: The stage prompt names the test case that a change invalidates
The planner prompt SHALL require a behavior group that changes a source file and names an existing test module to name each test case of that module whose assertion the change invalidates.

#### Scenario: A behavior group names an existing test module
- **WHEN** A behavior group changes `src/devops_cli/roadmap/stage/stage_probe.py` and names `tests/roadmap/stage/test_roadmap_stage_probe.py`.
- **THEN** The prompt requires the group to name each case of that module whose assertion the change breaks.

### Requirement: The stage prompt says when a group updates no existing test case
The planner prompt SHALL require a group that names an existing test module and invalidates no assertion in it to state that it updates no existing test case.

#### Scenario: A group only adds a case
- **WHEN** A group adds a case to an existing test module and changes no assertion of that module.
- **THEN** The prompt requires the group to state that it updates no existing test case.
