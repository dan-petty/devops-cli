## MODIFIED Requirements

### Requirement: The plan names files that exist at the staged commit
The job SHALL check each path of the reply against the tracked files of the staged commit: the paths of `reads` and `changes`, the paths in the code spans of the tasks, and the paths in `verify`. A path SHALL pass when the commit holds it, or when `creates` of its group or of an earlier group lists it. A missing path SHALL go back to the model once, with the files of the commit that have the same file name. When a later group lists the missing path in `creates`, the problem SHALL name the group that reads it and the first later group that creates it. A second reply with a missing path SHALL stop the item and open no draft pull request.

#### Scenario: A test file that moved
- **WHEN** a group changes `tests/test_scanner_tool_executor.py` and the commit holds `tests/security/test_scanner_tool_executor.py`
- **THEN** the job asks the model again, and the problem names the missing path and lists `tests/security/test_scanner_tool_executor.py`

#### Scenario: The second reply has a missing path
- **WHEN** the second reply still names `tests/test_scanner_tool_executor.py`
- **THEN** the job stops the item with the problem, pushes no branch and opens no draft pull request

#### Scenario: A path in a task or in a verify command
- **WHEN** a code span of a task or the `verify` command of a group names a file that the commit lacks and no group up to it creates
- **THEN** the problem names that file

#### Scenario: A created path
- **WHEN** a group changes `tests/test_new.py`, lists it in `creates`, and a later group reads it
- **THEN** the job finds no missing path

#### Scenario: A path that only a later group creates
- **WHEN** group 1 reads `tests/test_new.py` and only group 2 lists it in `creates`
- **THEN** the problem names group 1 and group 2, and tells the model to move group 2 before group 1

#### Scenario: A word that is no path
- **WHEN** a code span holds `status/blocked`, `--strict` or `uv run devops ci docs`
- **THEN** the job finds no missing path

#### Scenario: A name with no folder
- **WHEN** a code span of a task or the `verify` command holds `ruff.toml` or `grep step_files.py`
- **THEN** the job finds no missing path

#### Scenario: A path of reads or changes with no folder
- **WHEN** `reads` or `changes` holds `ruff.toml`
- **THEN** the job checks it as a path
