## ADDED Requirements

### Requirement: The plan check refuses a path of its own change folder
`check_proposal` SHALL refuse a path under `openspec/changes/<change>/` in a group `changes` or in a code span of a task when `change` is the plan's own change folder.

#### Scenario: A group lists the plan proposal
- **WHEN** A behavior group lists `openspec/changes/3321-plan-check/proposal.md` in `changes`, and `check_proposal` receives `change='3321-plan-check'`.
- **THEN** `check_proposal` returns one problem that names the path and the own change folder.

#### Scenario: A task names the plan tasks file
- **WHEN** A behavior group's `implementation` names `openspec/changes/3321-plan-check/tasks.md` in a code span, and `check_proposal` receives `change='3321-plan-check'`.
- **THEN** `check_proposal` returns one problem that names the group and the path.

#### Scenario: A group names another change folder
- **WHEN** A behavior group changes `openspec/changes/3307-other/proposal.md`, and `check_proposal` receives `change='3321-plan-check'`.
- **THEN** `check_proposal` returns no own-change problem.

### Requirement: A scenario that names code has a behavior test
`check_proposal` SHALL refuse a spec scenario that names a function or a file when no behavior group's `test` or `verify` names it and the scenario names no command.

#### Scenario: A scenario names `_loki_mode` and no task tests it
- **WHEN** A spec scenario's `then` names `_loki_mode` in a code span, and no behavior group's `test` or `verify` names `_loki_mode`.
- **THEN** `check_proposal` returns one problem that names the scenario and `_loki_mode`.

#### Scenario: A scenario that cites `helm template`
- **WHEN** A spec scenario's `then` names `_loki_mode` and `helm template` in code spans, and no behavior group's `test` names `_loki_mode`.
- **THEN** `check_proposal` returns no scenario problem.

#### Scenario: A behavior test names the function
- **WHEN** A spec scenario's `then` names `_loki_mode` in a code span, and a behavior group's `test` names `_loki_mode`.
- **THEN** `check_proposal` returns no scenario problem.

### Requirement: A quoted reference search names only covered files
`check_proposal` SHALL refuse each file that a quoted `References to` answer lists outside `openspec/changes/archive/` and that no group `changes` or `creates` path and no design decision names.

#### Scenario: A quoted search lists an untouched test file
- **WHEN** `feasibility` holds `References to 'SingleBinary': files 1, lines 1.` and `tests/commands/k8s/test_k8s.py: 1 (line 12)`, and no group or design decision names `tests/commands/k8s/test_k8s.py`.
- **THEN** `check_proposal` returns one problem that names `tests/commands/k8s/test_k8s.py`.

#### Scenario: A design decision names the test file
- **WHEN** The same `feasibility` lines are given, and a decision names `tests/commands/k8s/test_k8s.py` as left unchanged.
- **THEN** `check_proposal` returns no reference problem.

#### Scenario: An archived plan is skipped
- **WHEN** `feasibility` lists `openspec/changes/archive/2026-10-24-1000-old/proposal.md` in a quoted `References to` answer.
- **THEN** `check_proposal` returns no reference problem.
