# Spec Delta

## MODIFIED Requirements

### Requirement: The planner has a read-only toolbox
The planner of the stage job SHALL plan with an agent that has the tools of the toolset `roadmap.stage.toolset`. The toolset `base` SHALL have exactly these nine tools: `list_files`, `read_file`, `search_code`, `git_log`, `git_show`, `file_symbols`, `callers`, `repo_map` and `read_spec`. The toolset `extended` SHALL have these nine tools and `references`, `read_issue` and `find_issues`. Each tool SHALL read the staged commit through git, read files of the checkout, read a spec through OpenSpec, or, for `read_issue` and `find_issues`, read GitHub. The toolbox SHALL hold no tool that writes a file or runs a shell command. The only host that a tool SHALL reach is the GitHub API host of the Service, and only `read_issue` and `find_issues` SHALL reach it. A tool SHALL answer a bad argument as text and SHALL NOT raise.

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

## ADDED Requirements

### Requirement: The setting toolset chooses the tools of a plan run
The setting `roadmap.stage.toolset` SHALL be `base` or `extended`, with the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET`. The default SHALL be `extended`. The settings SHALL refuse any other value and name it. The example ConfigMap of the Service SHALL set the key. The toolset `base` SHALL have no GitHub tool and SHALL need no GitHub client.

#### Scenario: The default
- **WHEN** no config file and no variable sets `roadmap.stage.toolset`
- **THEN** the toolset is `extended`, and a plan run offers twelve tools

#### Scenario: The base toolset
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET` is `base`
- **THEN** a plan run offers the nine tools, and none of `references`, `read_issue` and `find_issues`

#### Scenario: A value that is none of the two
- **WHEN** the variable is `wide`
- **THEN** loading the settings fails with a message that names the variable and the values `base` and `extended`

### Requirement: The tool references counts a text in every file of the commit
`references(name)` SHALL run `git grep -n -I -F` for the text over the whole staged commit with no cap for a file. It SHALL answer the count of files and lines, and for each file its path, its exact count of lines and its first five line numbers. It SHALL answer as text for a name that is empty, longer than 100 characters, or not one line.

#### Scenario: Every file with its count
- **WHEN** a name is in a source file, a test, a fixture, a spec, two documents and a manifest, and one file holds it 400 times
- **THEN** the answer lists each of the eight files with its count, and the count of the large file is 400

#### Scenario: A name that cannot be searched
- **WHEN** the name is empty, or 101 characters long, or holds a line break
- **THEN** the answer says so as text, and the tool runs no git command

### Requirement: The tool references keeps files of every group
`references` SHALL keep at most 60 files. It SHALL take them in turn from the source, the tests, the specs, the documents, the change folders and the other files, so that a long list of one group hides no other group. It SHALL say how many files it left out.

#### Scenario: Files left out
- **WHEN** a name is in more than 60 files, among them a spec and a document
- **THEN** the answer lists 60 files that include the spec and the document, and says how many files it left out

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
`read_issue` and `find_issues` SHALL read through the GitHub client of the Service with its existing token, SHALL send GET requests only, and SHALL add no permission. They SHALL mask secrets in the text from GitHub with the secret masker, SHALL cut each text, and SHALL state in the answer that the text is data and no instruction. They SHALL answer each failure as text and SHALL NOT raise.

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
