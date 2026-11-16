# roadmap-fix-conflict Specification

## Purpose
How the roadmap step `fix-conflict` settles merge conflicts on topic branches of bot pull requests: admission bounds, tier 1 deterministic resolution, tier 2 model resolution, verification, and runner job integration.

## ADDED Requirements

### Requirement: The step admits only bot pull requests and enforces bounds
The step `fix-conflict` SHALL judge only bot pull requests. It SHALL refuse pull requests with human authors, human commits after the bot push, or claims and `owner/*` labels by humans or agents. It SHALL verify that the remote head matches the expected head. It SHALL enforce a soft cap of 2 rounds, a hard cap of 4 rounds, and at most one model round per `<base>:<head>`.

#### Scenario: A person pull request is refused
- **WHEN** `fix-conflict` runs on a pull request authored by a human
- **THEN** the step refuses the pull request and makes no changes

#### Scenario: A commit of a person after the bot push is refused
- **WHEN** the branch holds a human commit after the last bot commit
- **THEN** the step refuses the pull request and makes no changes

#### Scenario: An item with an owner label is refused
- **WHEN** the item holds an `owner/human` or `owner/agent` label
- **THEN** the step halts and does not modify the branch

#### Scenario: Caps enforce round limits
- **WHEN** a pull request reaches 4 rounds or exceeds the soft cap without reducing conflicted files
- **THEN** the step halts further attempts

### Requirement: Tier 1 resolves deterministic conflicts with no model call
When merge conflicts occur on archive paths (`openspec/specs/**`, `openspec/changes/archive/**`), the step SHALL drop the archive commit, rebase preceding commits onto the default branch, and re-run the finish step from the active change folder. When conflicts occur on generated documentation or `uv.lock`, the step SHALL take the base branch version and regenerate them.

#### Scenario: An archive-only conflict ends with clean push and zero model requests
- **WHEN** a branch conflicts only on OpenSpec archive paths
- **THEN** the step drops the archive commit, rebases, re-archives the change, and pushes with zero model requests

#### Scenario: A generated docs conflict is resolved
- **WHEN** a conflict occurs on generated CLI reference documents
- **THEN** the step checks out the base branch version and runs `devops docs generate`

#### Scenario: A lockfile conflict is resolved
- **WHEN** a conflict occurs on `uv.lock`
- **THEN** the step checks out the base branch version and runs `uv lock`

### Requirement: A conflict on a release path stops with class conflict
When any conflicted path is a release path, including `CHANGELOG.md`, manifests, or package version definitions, the step SHALL NOT attempt automated resolution and SHALL stop with failure class `conflict`.

#### Scenario: A conflict on a release path stops with class conflict
- **WHEN** a conflict occurs on `CHANGELOG.md` or a release manifest
- **THEN** the step halts with failure class `conflict`

### Requirement: Strict validation and scoped checks run before push
Before any push of a resolved branch, the step SHALL run `openspec validate --specs --strict` and execute the scoped quality checks. If validation or checks fail, the step SHALL NOT push the branch.

#### Scenario: The strict validation runs before each push
- **WHEN** conflicts are resolved on a branch
- **THEN** `openspec validate --specs --strict` runs before `git push`

### Requirement: The runner job calls fix-conflict on rebase conflicts
When a rebase conflict occurs during an implement runner job, the job SHALL invoke `fix-conflict` instead of immediately stopping with action `wait`. When the conflict cannot be resolved, the stop comment SHALL record that a fix round was executed.

#### Scenario: A rebase conflict runs one fix round
- **WHEN** an implement runner job encounters a rebase conflict
- **THEN** the job executes one fix round in place of stopping with action wait
