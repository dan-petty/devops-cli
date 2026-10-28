# review-merged-code Specification

## Purpose
What a review session records about the checkout that it read when it started, and when the session is on merged code: a clean path review at a commit that `origin/main` holds.

## Requirements

### Requirement: A review session records the checkout it read
When a review starts, the session SHALL record in findings.json and candidates.json the commit of the checkout that holds its target, as `checkout.head`, and whether the working tree of that checkout had a change, as `checkout.clean`. An untracked file SHALL count as a change. A target outside any checkout, or in a checkout with no commit, SHALL record no checkout.

#### Scenario: A path review of a clean checkout
- **WHEN** `devops review path <dir> --reporting-only` runs on a directory of a checkout with no change
- **THEN** findings.json and candidates.json hold `checkout` with the commit of `HEAD` and `clean` true

#### Scenario: A path review of a checkout with a change
- **WHEN** the review runs on a checkout with a changed tracked file, or with an untracked file
- **THEN** findings.json and candidates.json hold `checkout` with the commit of `HEAD` and `clean` false

#### Scenario: A target outside any checkout
- **WHEN** the checkout is read for a directory outside any checkout, or for a checkout with no commit
- **THEN** there is no checkout

### Requirement: A recorded head is a full commit name
The recorded `checkout.head` SHALL be a full commit name. A value that is an option, a symbolic name, an abbreviated name or upper-case hexadecimal SHALL be refused.

#### Scenario: findings.json names an option as the head
- **WHEN** a checkout is read with the head `--upload-pack=touch x`
- **THEN** it is refused with a validation error

### Requirement: Only a clean path review at a commit on main is on merged code
A session SHALL be on merged code only when its subject type is `path`, its checkout was clean, and `origin/main` in the given repository holds its head. A session with no checkout SHALL not be on merged code. A head that the repository does not hold SHALL raise `GitOperationError`.

#### Scenario: Each target type and tree state
- **WHEN** the predicate decides a `path` session of a clean tree at a commit on `origin/main`, a `pr` session, a `branch` session, a `path` session of a dirty tree, and a `path` session at a commit only on a topic branch
- **THEN** only the first is on merged code

#### Scenario: A commit the repository does not hold
- **WHEN** the predicate decides a clean `path` session whose head the repository does not hold
- **THEN** it raises `GitOperationError` with exit code 1 and error code `GIT_OPERATION_ERROR`

### Requirement: A verdict keeps the checkout
`devops review verify` SHALL keep the session's `checkout` when it rewrites findings.json.

#### Scenario: A person verifies a finding
- **WHEN** `devops review verify` sets a verdict on a finding of a session that records a checkout
- **THEN** findings.json still holds the same checkout

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
