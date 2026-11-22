## MODIFIED Requirements

### Requirement: The leftover processes end before each part of a network git call
`OriginGit` SHALL end every leftover process before it makes the new folder, and again just before the call with the token.

#### Scenario: The order of the calls
- **WHEN** the job reads the heads of a branch
- **THEN** the leftover processes end before the new folder is made, again after the new git folder is ready, and only then the read with the token runs

#### Scenario: A link at the shallow file before the call
- **WHEN** the `shallow` file of the clone is a link, and the job reads the heads of a branch in a runner
- **THEN** the leftover processes end first, the call raises `GitSettingsError` that names `shallow`, and the read with the token does not run

## REMOVED Requirements

### Requirement: The new git folder of a shallow clone gets its shallow file
**Reason**: `OriginGit` makes no fetch now: fix-conflict pushes from a new repository (#6703), and only the withdraw of the review step reads the heads and deletes a branch. No call changes the `shallow` file, so no write-back is left.
**Migration**: The requirement "The new git folder of a shallow clone gets a copy of its shallow file" holds the copy and the link rule.

## ADDED Requirements

### Requirement: The new git folder of a shallow clone gets a copy of its shallow file
The new git folder of a network call SHALL get a copy of the `shallow` file of a shallow clone, which the job SHALL open with `O_NOFOLLOW`. A link, or anything but a regular file, at that place SHALL raise `GitSettingsError` that names `shallow`.

#### Scenario: A push from a shallow clone
- **WHEN** the clone was made with `--depth 1`, and the job pushes a new commit of the clone
- **THEN** `origin` holds the new commit on the branch, and the clone stays shallow

#### Scenario: A link at the shallow file
- **WHEN** the `shallow` file of the clone is a link, and the job reads the heads of `main`
- **THEN** the call raises `GitSettingsError` that names `shallow`
