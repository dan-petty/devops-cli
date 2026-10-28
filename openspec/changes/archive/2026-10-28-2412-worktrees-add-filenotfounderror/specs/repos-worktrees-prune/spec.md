# Spec Delta

## MODIFIED Requirements

### Requirement: A removable worktree reports its size
For each worktree that `prune` removes or would remove, the report SHALL give the size of its directory in bytes as `size_bytes`, and the table SHALL show the size beside the worktree and the total in its last line. A worktree whose directory is missing SHALL have no size. When a file in the directory is deleted during measurement, it SHALL contribute 0 bytes and SHALL NOT cause an error.

#### Scenario: Preview
- **WHEN** the user runs `prune` and a worktree of 1 MB would be removed
- **THEN** the line of that worktree and the last line give the size

#### Scenario: JSON
- **WHEN** the user runs `prune --confirm --json` and a worktree is removed
- **THEN** its item has `size_bytes` as the number of bytes of the directory before the removal

#### Scenario: Missing directory
- **WHEN** the directory of a worktree is gone and the user runs `prune --json`
- **THEN** its item has a null `size_bytes`

#### Scenario: File deleted during directory size walk
- **WHEN** a file in a measured directory is deleted before its size is read
- **THEN** the directory size returns the sum of the remaining files without raising an error
