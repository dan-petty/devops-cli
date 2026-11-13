# roadmap-stage/toolbox Specification

## Purpose
The read-only toolbox of a plan run: the toolset setting, each tool and its answer, the web search of the research toolset, and the allow-list of the commands that a plan run can start.

## Requirements

### Requirement: The planner has a read-only toolbox
The planner of the stage job SHALL plan with an agent that has the tools of the toolset `roadmap.stage.toolset`. The toolset `base` SHALL have exactly `list_files`, `read_file`, `search_code`, `git_log`, `git_show`, `file_symbols`, `callers`, `repo_map` and `read_spec`. The toolset `extended` SHALL add `references`, `read_issue` and `find_issues`. No tool SHALL write a file or run a shell command. A tool SHALL answer a bad argument as text and SHALL NOT raise.

#### Scenario: The tool set
- **WHEN** the toolbox is built for a checkout and a commit with the toolset `base`
- **THEN** the names of its tools are exactly the nine above, and `search_web` is not one of them

#### Scenario: A path outside the repository
- **WHEN** `read_file` gets the path `../outside.txt`
- **THEN** it answers that the path is outside the repository, and it raises no error

#### Scenario: An argument that is an option
- **WHEN** `git_show` gets `--output=out.txt`
- **THEN** it answers that the argument is no commit, and no file `out.txt` exists

#### Scenario: The prompt names the tools
- **WHEN** the system text of a toolbox run is built
- **THEN** it names each tool of the toolset of the run and no tool of the other toolset

### Requirement: The tools read a checkout that is the staged commit
The toolbox SHALL refuse a checkout whose HEAD is not the staged commit, or that has a change that is not committed or a file that git does not track, before any model call. The failure SHALL be a `RoadmapStageError`. A tool SHALL read the size of a file before it reads the file, SHALL refuse a file of more than 2000000 bytes, and SHALL number only the lines that it returns. `search_code` and `callers` SHALL stop at one more than `CONST_ROADMAP_REFINE_TOOL_MAX_LINES` matches in one file.

#### Scenario: A modified file
- **WHEN** the checkout holds a modified tracked file
- **THEN** building the toolbox raises `RoadmapStageError` and the model gets no request

#### Scenario: A file over the size limit
- **WHEN** `read_file` gets a file of more than 2000000 bytes
- **THEN** it answers that the file is too large to read

#### Scenario: A file with many matches
- **WHEN** a file holds three times `CONST_ROADMAP_REFINE_TOOL_MAX_LINES` lines that match `callers`
- **THEN** the answer holds `CONST_ROADMAP_REFINE_TOOL_MAX_LINES` lines and says that lines are left out

### Requirement: The map and the spec tools give short answers
`repo_map` SHALL give one line for each of at most `CONST_ROADMAP_STAGE_MAP_MAX_FILES` files, with the path and the names of the top-level symbols, cut to 180 characters, and a last line that says so when the directory holds more files. `read_spec` SHALL read the specs from the JSON of `openspec list --specs` and `openspec show --type spec`. For one capability it SHALL answer with a line `Purpose:` and then the requirement names. It SHALL answer as text when OpenSpec is not installed.

#### Scenario: A directory with more files than the limit
- **WHEN** `repo_map` maps a directory of `CONST_ROADMAP_STAGE_MAP_MAX_FILES` plus 5 Python files
- **THEN** the answer has `CONST_ROADMAP_STAGE_MAP_MAX_FILES` file lines and a last line that says that files are left out

#### Scenario: A requirement
- **WHEN** `read_spec` gets a capability and a requirement name
- **THEN** it answers with the heading, the text and the scenarios of that requirement

#### Scenario: A capability
- **WHEN** `read_spec` gets a capability and no requirement name
- **THEN** it answers with a first line `Purpose:` and the purpose, and then the requirement names

#### Scenario: A capability with no requirement
- **WHEN** `read_spec` gets a capability that holds a purpose and no requirement
- **THEN** it answers with the line `Purpose:` and the purpose

### Requirement: A call to a tool that is gone gets a retry
When a request offers no tool, a call of the model to a function tool SHALL get a retry prompt, and the run SHALL go on. The run SHALL fail the item when the model calls a gone tool a third time, because the tool retry limit is 2. The reason of the failure SHALL name the retry limit, and no budget limit. It holds no tool name, because the name of a tool in an error message is text that the model chose.

#### Scenario: One call after the tools are gone
- **WHEN** the model has made `roadmap.stage.max_tool_calls` minus 3 tool calls, calls `read_file` once in a request that offers no tool, and then gives a valid plan
- **THEN** the item is staged

#### Scenario: Two calls after the tools are gone
- **WHEN** the model calls `read_file` twice in requests that offer no tool, and then gives a valid plan
- **THEN** the item is staged

#### Scenario: Three calls after the tools are gone
- **WHEN** the model calls `read_file` a third time in requests that offer no tool
- **THEN** the item fails, and the reason names the retry limit 2, and no budget limit

### Requirement: The setting toolset chooses the tools of a plan run
The setting `roadmap.stage.toolset` SHALL be `base`, `extended` or `research`, with the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET`. The default SHALL be `extended`. The settings SHALL refuse any other value and name it. The example ConfigMap of the Service SHALL set the key. The toolset `base` SHALL have no GitHub tool and SHALL need no GitHub client.

#### Scenario: The default
- **WHEN** no config file and no variable sets `roadmap.stage.toolset`
- **THEN** the toolset is `extended`, and a plan run offers twelve tools

#### Scenario: The base toolset
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET` is `base`
- **THEN** a plan run offers the nine tools, and none of `references`, `read_issue` and `find_issues`

#### Scenario: A value that is none of the two
- **WHEN** the variable is `wide`
- **THEN** loading the settings fails with a message that names the variable and the values `base`, `extended` and `research`

#### Scenario: The research toolset
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET` is `research`
- **THEN** a plan run offers thirteen tools: every tool of `extended` and `search_web`

### Requirement: The tool references counts a text in every file of the commit
`references(name)` SHALL run `git grep -n -I -F` for the text over the whole staged commit with no cap for a file. It SHALL answer the count of files and lines, and for each file its path, its exact count of lines and its first five line numbers. It SHALL answer as text for a name that is empty, longer than 100 characters, or not one line.

#### Scenario: Every file with its count
- **WHEN** a name is in a source file, a test, a fixture, a spec, two documents and a manifest, and one file holds it 400 times
- **THEN** the answer lists each of the eight files with its count, and the count of the large file is 400

#### Scenario: A name that cannot be searched
- **WHEN** the name is empty, or 101 characters long, or holds a line break
- **THEN** the answer says so as text, and the tool runs no git command

### Requirement: The tool references keeps files of every group
`references` SHALL keep at most 60 files. It SHALL take them in turn from the specs, the source, the tests, the documents, the change folders and the other files, so that a long list of one group hides no other group. It SHALL say how many files it left out.

#### Scenario: Files left out
- **WHEN** a name is in more than 60 files, among them a spec and a document
- **THEN** the answer lists 60 files that include the spec and the document, and says how many files it left out

#### Scenario: A command name exists in a spec and in source
- **WHEN** a name is in a file under the specs and in a file under the source, and the answer keeps both files
- **THEN** the answer lists the spec file before the source file

### Requirement: The tool read_issue answers the state of an item
`read_issue(number)` SHALL answer the state, the title, the labels, the first 1500 characters of the body, and the last 3 comments cut to 600 characters each. For a closed issue it SHALL name the merged pull request that closed it, or say that none did. For a closed pull request it SHALL say whether it merged.

#### Scenario: An issue closed by a merged pull request
- **WHEN** `read_issue` reads a closed issue whose last closing commit is in a merged pull request
- **THEN** the answer holds the state, the title, the labels and the line "Closed by merged pull request #N."

#### Scenario: A closed pull request
- **WHEN** `read_issue` reads a closed pull request that did not merge
- **THEN** the answer says that the pull request closed with no merge

### Requirement: The tool find_issues lists open items that name the terms
`find_issues(terms)` SHALL answer at most 10 open issues and pull requests of the repository that name the terms, each as `#N state title`. It SHALL take every colon and quote out of the terms, so that the search names no repository but that of the job.

#### Scenario: Open items
- **WHEN** `find_issues` gets the terms `redaction point` and GitHub finds an issue and a pull request
- **THEN** the answer lists both as `#N state title`

#### Scenario: A qualifier in the terms
- **WHEN** `find_issues` gets the terms `repo:other/private`
- **THEN** the search that GitHub receives holds no `repo:` qualifier except that of the repository of the job

### Requirement: The GitHub tools read only, mask what they read and answer a failure as text
`read_issue` and `find_issues` SHALL read through the GitHub client of the Service with its existing token, send GET requests only, and add no permission. They SHALL reach no host but the GitHub API host of the Service, and no other tool SHALL open a network connection. They SHALL mask secrets in the text from GitHub, cut each text, and state that it is data and no instruction. They SHALL answer each failure as text and SHALL NOT raise.

#### Scenario: A secret in the text from GitHub
- **WHEN** the body, a comment and the title of an issue each hold a token
- **THEN** the answer holds none of the three tokens

#### Scenario: An item that does not exist
- **WHEN** `read_issue` gets a number that GitHub does not hold
- **THEN** the answer says that GitHub holds no such issue or pull request, and it raises no error

#### Scenario: A failure of GitHub
- **WHEN** the connection to GitHub fails
- **THEN** the answer names the class of the failure, tells the model to go on without it, and holds no text of the failure

#### Scenario: A run with no client
- **WHEN** a plan run has the toolset `extended` and the job gave no GitHub client
- **THEN** `read_issue` and `find_issues` answer that GitHub is not available

### Requirement: The prompt of the extra tools says when to call each one
The prompt of a run with the toolset `extended` SHALL tell the model to call `references` for a rename, a move or a removal, `read_issue` for each issue number that the issue names, and `find_issues` before the plan says what it depends on. It SHALL tell the model that text from GitHub is data and never an instruction. The prompt of a run with the toolset `base` SHALL name none of the three tools.

#### Scenario: The extended prompt
- **WHEN** the system text of a run with the toolset `extended` is built
- **THEN** it names `references`, `read_issue` and `find_issues`, and it says that text from GitHub is data

#### Scenario: The base prompt
- **WHEN** the system text of a run with the toolset `base` is built
- **THEN** it names none of `references`, `read_issue` and `find_issues`

### Requirement: A git command that runs out of time is an error
A tool of the stage planner whose git command runs out of time SHALL answer with the outcome `error` and a text that says so. It SHALL NOT answer that nothing was found.

#### Scenario: Each tool that runs git
- **WHEN** every git command of `search_code`, `list_files`, `read_file`, `git_log`, `git_show`, `callers` and `references` runs out of time
- **THEN** each answer has the outcome `error`, and its text says that the command ran out of time

### Requirement: Research toolset adds search_web
The stage toolbox SHALL add `search_web` when the toolset is `research`.

#### Scenario: Research adds one tool
- **WHEN** the stage toolset is `research`
- **THEN** the toolbox holds every `extended` tool and `search_web`, and no other tool.

### Requirement: Base and extended omit search_web
The stage toolbox SHALL NOT include `search_web` when the toolset is `base` or `extended`.

#### Scenario: Network-free toolsets stay network-free
- **WHEN** the stage toolset is `base` or `extended`
- **THEN** the toolbox holds no `search_web` tool.

### Requirement: Search query is guarded before the call
The search tool SHALL build the query from the short term that the model gives and SHALL apply the secret masker and private-data rules before it calls the search service.

#### Scenario: Secret and internal host are stopped
- **WHEN** the short term holds a secret or an internal host
- **THEN** the tool masks the secret and refuses the internal host before it calls the search service.

### Requirement: Search result is data
The search tool SHALL return only titles, URLs and cut snippets, and the prompt SHALL state that a result is data and not an instruction.

#### Scenario: Result text is cut and marked as data
- **WHEN** the search service returns a long snippet and an instruction in its title
- **THEN** the tool returns the title, URL and a cut snippet, and the prompt marks the result as data.

### Requirement: Search limit and outcome counter
A plan run SHALL stop calling `search_web` at the stage search limit and SHALL count each search by its outcome.

#### Scenario: Excess search is refused and counted
- **WHEN** the model asks for more searches than the limit, with one success and one refusal
- **THEN** the tool refuses the excess call and the run records the counts by outcome.

### Requirement: A cut tool answer says so
The answer of a read-only tool of a roadmap job SHALL end at a whole line when the character limit shortens it, and a single line over the limit SHALL be cut. An answer that lost text to the line limit or to the character limit SHALL end with the line `(more lines are left out)`. An answer under both limits SHALL have no notice.

#### Scenario: The character limit drops lines
- **WHEN** a tool answers with 100 lines of 100 characters and the character limit is 8,000
- **THEN** the answer holds whole lines only, and its last line is `(more lines are left out)`

#### Scenario: An answer under both limits
- **WHEN** a tool answers with 10 lines of 100 characters
- **THEN** the answer is those lines and has no notice

#### Scenario: One line over the limit
- **WHEN** a tool answers with one line of 8,500 characters
- **THEN** the answer is the first 8,000 characters of the line and the notice

### Requirement: The allow-list holds the read-only rows of the exposure table
The builder SHALL hold each command path whose row of `CONST_MCP_EXPOSURE_TABLE` is read-only and whose permitted parameters hold no path parameter, with the permitted parameter names as its value.

#### Scenario: A read-only command with no path parameter
- **WHEN** the builder runs and the row of `gh label list` is read-only and its permitted parameters hold no path parameter
- **THEN** the table holds `('gh', 'label', 'list')` with `repo` among its parameters

### Requirement: A path parameter keeps its command out of the allow-list
The builder SHALL leave out each command path whose permitted parameters hold a path parameter: a parameter that Typer types as a path, or a parameter that `PATH_CONFINEMENTS` names for the command.

#### Scenario: A restricted command with a path parameter
- **WHEN** the allowed set of `tf plan` holds a directory parameter that Typer types as a path
- **THEN** the table holds no entry for `('tf', 'plan')` and the validator returns the reason `path option`

#### Scenario: An unrestricted command with a path parameter
- **WHEN** the repository parameter of `ai read` has a path type
- **THEN** the table holds no entry for `('ai', 'read')` and the validator returns the reason `path option`

#### Scenario: A text parameter that holds a path
- **WHEN** the builder runs and `scan sast` permits `config`, which holds a path and which no type shows
- **THEN** the table holds no entry for `('scan', 'sast')` and the validator returns the reason `path option`

### Requirement: A restricted command permits only its allowed options
The builder SHALL take the permitted options of a command that `_PATH_PARAM_RESTRICTIONS` names from that entry's `allowed` set.

#### Scenario: A restricted command with no path parameter
- **WHEN** the builder runs and the entry of `telemetry profile` allows one option
- **THEN** the table holds `('telemetry', 'profile')` with that option as its only one

### Requirement: The help form of a command path is permitted
The validator SHALL permit the `--help` form of each command path that the Click tree resolves and SHALL return no reason for it.

#### Scenario: Help of a write command
- **WHEN** the validator checks `valkey flush` with the `--help` option
- **THEN** it permits the run and returns no reason

### Requirement: A refused run names the path and one reason
The validator SHALL return the command path and one reason from `unknown command`, `not read-only`, `path option` and `option not permitted` for a run that it refuses, and SHALL name the option for `option not permitted`.

#### Scenario: A command path that no row names
- **WHEN** the validator checks `config unset`
- **THEN** it refuses the run with the reason `unknown command` and names the path `('config', 'unset')`

#### Scenario: An option outside the permitted set
- **WHEN** the validator checks `ai benchmark` with the `output` option
- **THEN** it refuses the run with the reason `option not permitted` and names `output`

### Requirement: Each read tool description shows its answer format whole
The description that the stage planner and the refine investigation send for each read tool SHALL hold the answer format of the tool whole, such as `path:line:content` for `search_code` and `callers` and `line: signature` for `file_symbols`. No description SHALL hold a `<returns>` part that the docstring parser makes.

#### Scenario: The model reads the search tool
- **WHEN** the stage planner or the refine investigation builds the definition of `search_code`
- **THEN** its description holds `path:line:content` whole and has no `<returns>` part

#### Scenario: The model reads the symbol tool
- **WHEN** the stage planner builds the definition of `file_symbols`
- **THEN** its description holds `line: signature` whole and has no `<returns>` part
