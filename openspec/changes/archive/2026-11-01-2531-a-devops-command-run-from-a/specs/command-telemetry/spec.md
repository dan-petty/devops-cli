## ADDED Requirements

### Requirement: A span starts without VCS attributes when the working directory is gone
The telemetry client SHALL start a span, with no `vcs.*` attribute and no exception, when the working directory of the process no longer exists. When the working directory exists and lies inside a git repository, the span SHALL hold the branch and the revision of that repository in its `vcs.*` attributes.

#### Scenario: The working directory was removed
- **WHEN** the working directory of the process is removed and a client starts a span
- **THEN** the span starts and holds no `vcs.ref.name`, `vcs.branch`, `vcs.revision_id` and `vcs.commit` attribute

#### Scenario: The working directory is inside a git repository
- **WHEN** the working directory holds a `.git` directory whose `HEAD` names a branch and whose branch file holds a revision, and a client starts a span
- **THEN** the span holds that branch in `vcs.ref.name` and `vcs.branch`, and that revision in `vcs.revision_id` and `vcs.commit`
