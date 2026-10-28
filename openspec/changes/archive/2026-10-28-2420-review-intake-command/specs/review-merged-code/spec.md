## ADDED Requirements

### Requirement: A session that is not on merged code says why
`why_not_on_merged_code` SHALL give no reason for a session that is on merged code, and otherwise the first reason that holds, in this order: the subject type is not `path`; the session records no checkout; the working tree had a change; `origin/main` in the repository does not hold the commit.

#### Scenario: Each reason
- **WHEN** the reason is asked for a `pr` session, a `path` session with no checkout, a `path` session of a dirty tree, a clean `path` session at a commit only on a topic branch, and a clean `path` session at a commit on `origin/main`
- **THEN** the reasons name the target type `pr`, the missing checkout, the changed tree, and the commit that `origin/main` does not hold, and the last session has no reason

### Requirement: `review path` names the hand-off
When `devops review path` keeps a session of a clean tree with at least one qualifying finding, it SHALL print the count of qualifying findings and `devops review intake <session> --plan`. It SHALL run no git, send no request and call no model for that line. A session with no qualifying finding, or of a tree with a change, SHALL print no such line.

#### Scenario: A clean session with two qualifying findings
- **WHEN** the line is made for a clean `path` session with two qualifying findings and one invalidated finding
- **THEN** the line names 2 findings and `devops review intake <session> --plan`

#### Scenario: A session of a tree with a change
- **WHEN** the line is made for a `path` session of a dirty tree with qualifying findings
- **THEN** there is no line
