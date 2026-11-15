## ADDED Requirements

### Requirement: The second attempt adds the repository map
The second attempt of a step SHALL add a section headed `# Repository map` to its message. The section SHALL hold one line for each file that the reason of the previous attempt names and each file that the group names, and no other file. A line SHALL hold the path and the names of the top-level symbols, in the form of the `repo_map` tool. The section SHALL hold at most `CONST_ROADMAP_STAGE_MAP_MAX_FILES` files and SHALL be absent when it holds none.

#### Scenario: A failure that names a file
- **WHEN** the reason of the first attempt names a file of the checkout
- **THEN** the message of the second attempt holds the section `# Repository map` with the entry of that file

#### Scenario: A failure that names no file
- **WHEN** the reason names no file and the group names no file
- **THEN** the message of the second attempt holds no `# Repository map` section
