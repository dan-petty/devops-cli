## ADDED Requirements

### Requirement: The job probes a claimed missing check in a helper of its call site
After the model reply and before it writes a branch or a pull request, the stage job SHALL read the body of a call site that a plan text says runs no named check, and the body of each helper that the call site calls in its file. The job SHALL write one line that names the path and the line of a check that it finds there, and SHALL send no model request for the read. A claim that names no call site and no named check SHALL add no line.

#### Scenario: A helper of the call site holds the check
- **WHEN** a plan text says that the call site `_publish` runs no `title_problems` check, and `_publish` calls `_delivery_title`, whose body calls `title_problems`
- **THEN** the probe line names `title_problems` at the path and the line of its call in `_delivery_title`

#### Scenario: A claim with no cited call site
- **WHEN** a plan says that a check is missing but names no call site and no check
- **THEN** the probe adds no line and the stage job plans the item as before

#### Scenario: A claim is probed with no model call
- **WHEN** a plan claims a missing check and the stage job probes it
- **THEN** the stage job sends no model request for the read

### Requirement: The job searches the base tree for a claimed missing check
The stage job SHALL search the source files of the staging commit for a named check that a plan text says is missing, when the cited call site and its helpers do not hold it. The search SHALL use the git commands that the probe of the item has left, SHALL run only read-only commands at the staging commit, and SHALL list a claim as skipped when no command is left.

#### Scenario: A check that only another file holds
- **WHEN** a plan says that a call site runs no named check, and only another source file of the staging commit holds that check
- **THEN** the probe line names the path and the line of the check in that file

#### Scenario: The bound leaves a claim unprobed
- **WHEN** a plan claims more missing checks than the commands that are left
- **THEN** the probe lists the claim as skipped and runs no further command
