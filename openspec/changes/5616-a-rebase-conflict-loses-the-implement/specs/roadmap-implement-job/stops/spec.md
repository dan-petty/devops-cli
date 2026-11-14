## MODIFIED Requirements

### Requirement: A conflict stop names the conflicted files
On a conflict the job SHALL read the unmerged files with `git diff --name-only --diff-filter=U` before it aborts the rebase. The stop comment SHALL name each file, the item branch and the count of passed task groups on the branch. The job record SHALL hold the files as `implement.conflict`, and the next Job SHALL clear it. The job SHALL mask each path and list at most `CONST_ROADMAP_IMPLEMENT_REASON_PATHS` paths, and state how many paths the cut left out.

#### Scenario: A conflict at the start of a run
- **WHEN** the staged branch conflicts with the default branch in a real git repository when the job rebases at the start of the run
- **THEN** the item stops with the class `conflict`, and the comment names each conflicted file, the item branch and the count of passed task groups on it

#### Scenario: A conflict before the push
- **WHEN** the default branch gains a change that conflicts with the branch when the job rebases before the push
- **THEN** the item stops with the class `conflict`, and the comment names each conflicted file, the item branch and the count of passed task groups on it

#### Scenario: The count of passed groups
- **WHEN** a conflict stops an item of four task groups whose first two are ticked on the branch
- **THEN** the comment states the count of two passed task groups and names the item branch

#### Scenario: The record holds the files until a retry
- **WHEN** a conflict stops the item, and a person then comments `implement: retry`
- **THEN** the job record holds each file after the stop, and holds none after the first record write of the next Job

#### Scenario: A clear rule keeps the files
- **WHEN** a conflict stops the item and a clear rule of the Service removes the stop
- **THEN** the job record still holds each file

#### Scenario: A list above the limit
- **WHEN** the conflict holds more files than `CONST_ROADMAP_IMPLEMENT_REASON_PATHS`
- **THEN** the comment names the files up to the limit and states the number of files left out

#### Scenario: A secret in a path
- **WHEN** a conflicted file path holds a token of a known secret
- **THEN** the comment and the record hold the masked path and not the token
