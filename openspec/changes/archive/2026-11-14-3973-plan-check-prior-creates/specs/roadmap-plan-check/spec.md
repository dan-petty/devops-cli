## MODIFIED Requirements

### Requirement: Plan-check reports a group that packs no file
The command SHALL report a `group-no-files` problem for each group that changes a file that exists and packs no file. A group that only creates files SHALL be no problem. A path that an earlier group of the same plan creates SHALL count as present for a later group.

#### Scenario: A group that packs no file is reported
- **WHEN** a group changes a file of the pull request head and no code span of its tasks names a file of the head
- **THEN** the output holds a `group-no-files` problem that names the group, and the exit code is 1.

#### Scenario: A group that only creates files is not reported
- **WHEN** each path that a group changes is a path that it creates
- **THEN** the output holds no `group-no-files` problem for that group.

#### Scenario: A later group changes the file of an earlier group
- **WHEN** group 1 creates a file and group 2 changes that file and creates nothing
- **THEN** the output holds no `group-no-files` problem for group 2.
