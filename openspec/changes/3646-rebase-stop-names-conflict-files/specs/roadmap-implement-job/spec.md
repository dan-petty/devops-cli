## ADDED Requirements

### Requirement: A conflict stop names the conflicted files
When a rebase stops the item on a conflict, the job SHALL read the unmerged files with `git diff --name-only --diff-filter=U` before it aborts the rebase. The stop comment SHALL name each file, the job record SHALL hold the files as `implement.conflict`, and a retry SHALL clear the record. The job SHALL mask each path, SHALL list at most `CONST_ROADMAP_IMPLEMENT_REASON_PATHS` paths, and SHALL state the number of paths that the cut left out.

#### Scenario: A conflict at the start of a run
- **WHEN** the staged branch conflicts with the default branch in a real git repository when the job rebases at the start of the run
- **THEN** the item stops with the class `conflict`, and the comment names each conflicted file

#### Scenario: A conflict before the push
- **WHEN** the default branch gains a change that conflicts with the branch when the job rebases before the push
- **THEN** the item stops with the class `conflict`, and the comment names each conflicted file

#### Scenario: The record holds the files until a retry
- **WHEN** a conflict stops the item, and a person then comments `implement: retry`
- **THEN** `implement.conflict` holds each file after the stop, and holds none after the retry starts the item

#### Scenario: A list above the limit
- **WHEN** the conflict holds more files than `CONST_ROADMAP_IMPLEMENT_REASON_PATHS`
- **THEN** the comment names the files up to the limit and states the number of files left out

#### Scenario: A secret in a path
- **WHEN** a conflicted file path holds a token that `mask_secrets` knows
- **THEN** the comment and the record hold the masked path and not the token
