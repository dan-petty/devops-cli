## ADDED Requirements

### Requirement: The stage check names the message file a task needs
The stage check SHALL return a problem that names `src/devops_cli/lang/en/messages.py` when a rendered task text of a group names `MESSAGES.roadmap` and no group lists that file in `changes`.

#### Scenario: A task text names a message without the message file
- **WHEN** A plan has a task text that names `MESSAGES.roadmap` and no group lists `src/devops_cli/lang/en/messages.py` in `changes`.
- **THEN** `content_problems` returns a problem that names `src/devops_cli/lang/en/messages.py`.

#### Scenario: A task text names a message with the message file
- **WHEN** A plan has a task text that names `MESSAGES.roadmap` and a group lists `src/devops_cli/lang/en/messages.py` in `changes`.
- **THEN** `content_problems` returns no problem about `src/devops_cli/lang/en/messages.py`.

#### Scenario: A task text names a dotted message entry
- **WHEN** A plan has a task text that names `MESSAGES.roadmap.some_entry` and no group lists `src/devops_cli/lang/en/messages.py` in `changes`.
- **THEN** `content_problems` returns a problem that names `src/devops_cli/lang/en/messages.py`.

### Requirement: The verification prompt names the missing path of a needed file
The verification prompt `src/devops_cli/ai/tasks/roadmap_stage_verify.md` SHALL name `missing_path` for a code change that needs a file that the plan does not change.

#### Scenario: The prompt names the missing path type
- **WHEN** The verification prompt `src/devops_cli/ai/tasks/roadmap_stage_verify.md` is read.
- **THEN** The prompt states that a code change that needs an unchanged file is a `missing_path` finding.
