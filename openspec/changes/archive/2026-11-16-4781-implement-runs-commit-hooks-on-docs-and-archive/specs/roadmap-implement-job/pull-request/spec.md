## ADDED Requirements

### Requirement: Commit stage runs before docs and archive commits
The job SHALL run the trusted commit stage on the staged changes of each commit that `_commit_if_changed` makes before `git commit`. When a fixer hook rewrites a file, the job SHALL stage the file, run the stage once more, and commit the rewritten file. When the stage fails on the second run, the job SHALL stop the item with the hook output, and make no docs or archive commit. When the commit holds no change, the job SHALL make no commit and run the stage zero times.

#### Scenario: Docs commit runs the stage and fixes whitespace
- **WHEN** the docs generator changes a generated file with trailing whitespace
- **THEN** the commit stage runs over the staged changes before `git commit`, trims the whitespace, and commits the cleaned file

#### Scenario: Hook failure on docs or archive commit stops the item
- **WHEN** the commit stage fails on staged changes and fails again after fixer files are staged
- **THEN** the item stops with the hook output in the stop comment, and no docs or archive commit is made

#### Scenario: Docs generator writes nothing
- **WHEN** the docs generator writes no file and the checkout holds no change
- **THEN** the job makes no commit and runs the commit stage zero times
