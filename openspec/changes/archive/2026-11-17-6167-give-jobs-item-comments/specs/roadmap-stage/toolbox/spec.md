## MODIFIED Requirements

### Requirement: The planner has a read-only toolbox
The planner of the stage job SHALL plan with an agent that has the tools of the toolset `roadmap.stage.toolset`. The toolset `base` SHALL have exactly `list_files`, `read_file`, `search_code`, `git_log`, `git_show`, `file_symbols`, `callers`, `repo_map`, `read_spec` and `read_comment`. The toolset `extended` SHALL add `references`, `read_issue` and `find_issues`. No tool SHALL write a file or run a shell command. A tool SHALL answer a bad argument as text and SHALL NOT raise.

#### Scenario: The tool set
- **WHEN** the toolbox is built for a checkout and a commit with the toolset `base`
- **THEN** the names of its tools are exactly the ten above, and `search_web` is not one of them

#### Scenario: A path outside the repository
- **WHEN** `read_file` gets the path `../outside.txt`
- **THEN** it answers that the path is outside the repository, and it raises no error

#### Scenario: An argument that is an option
- **WHEN** `git_show` gets `--output=out.txt`
- **THEN** it answers that the argument is no commit, and no file `out.txt` exists

#### Scenario: The prompt names the tools
- **WHEN** the system text of a toolbox run is built
- **THEN** it names each tool of the toolset of the run and no tool of the other toolset

### Requirement: The setting toolset chooses the tools of a plan run
The setting `roadmap.stage.toolset` SHALL be `base`, `extended` or `research`, with the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET`. The default SHALL be `extended`. The settings SHALL refuse any other value and name it. The example ConfigMap of the Service SHALL set the key. The toolset `base` SHALL have no GitHub tool and SHALL need no GitHub client.

#### Scenario: The default
- **WHEN** no config file and no variable sets `roadmap.stage.toolset`
- **THEN** the toolset is `extended`, and a plan run offers thirteen tools

#### Scenario: The base toolset
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET` is `base`
- **THEN** a plan run offers the ten tools, and none of `references`, `read_issue` and `find_issues`

#### Scenario: A value that is none of the two
- **WHEN** the variable is `wide`
- **THEN** loading the settings fails with a message that names the variable and the values `base`, `extended` and `research`

#### Scenario: The research toolset
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET` is `research`
- **THEN** a plan run offers fourteen tools: every tool of `extended` and `search_web`

## ADDED Requirements

### Requirement: The tool read_comment reads a comment of the item whole
`read_comment(number, start_line)` SHALL answer the whole text of comment `number` of the item in hand from line `start_line`, with its author, its time and its page. A line longer than `CONST_ROADMAP_COMMENT_LINE_CHARS` characters SHALL come as more numbered lines. An answer longer than the cap of a tool answer SHALL end with the call that reads the next page, so no text is lost. The tool SHALL read the comments that the job read for the item, and SHALL reach no host.

#### Scenario: A long comment
- **WHEN** `read_comment` reads a comment of 300 long lines
- **THEN** the first answer holds line 1 and names the call for the next line, and that call answers the next line

### Requirement: The tool read_comment lists the comments of the item
`read_comment` with no number SHALL list every comment of the item with its number, author, time and first line. A number that the item does not hold SHALL get an answer that names the numbers of its comments.

#### Scenario: The list of the comments
- **WHEN** `read_comment` gets no number for an item with two comments
- **THEN** the answer lists both, each with its number and its author

#### Scenario: A number that the item does not hold
- **WHEN** `read_comment` gets 4 for an item with one comment
- **THEN** the answer says that the item has no comment 4
