## ADDED Requirements

### Requirement: The planner has a read-only toolbox
The planner of the stage job SHALL plan with an agent that has exactly these tools: `list_files`, `read_file`, `search_code`, `git_log`, `git_show`, `file_symbols`, `callers`, `repo_map` and `read_spec`. Each tool SHALL read the staged commit through git, or read files of the checkout. The toolbox SHALL hold no tool that writes a file, runs a shell command or opens a network connection. A tool SHALL answer a bad argument as text and SHALL NOT raise.

#### Scenario: The tool set
- **WHEN** the toolbox is built for a checkout and a commit
- **THEN** the names of its tools are exactly the nine above, and `search_web` is not one of them

#### Scenario: A path outside the repository
- **WHEN** `read_file` gets the path `../outside.txt`
- **THEN** it answers that the path is outside the repository, and it raises no error

#### Scenario: An argument that is an option
- **WHEN** `git_show` gets `--output=out.txt`
- **THEN** it answers that the argument is no commit, and no file `out.txt` exists

#### Scenario: The prompt names the tools
- **WHEN** the system text of a toolbox run is built
- **THEN** it names each tool of the toolbox

### Requirement: A plan run has a budget
A plan run of the toolbox SHALL stop when it makes more than 30 tool calls or uses more than 50000 output tokens. The item SHALL then fail with a reason that names the limit that was hit. The job SHALL plan the other items, and SHALL open no draft pull request for the failed item.

#### Scenario: The tool call limit
- **WHEN** the model calls a tool 31 times in one plan run
- **THEN** the item fails, and the reason names `tool_calls_limit`

#### Scenario: The output token limit
- **WHEN** the replies of the model in one plan run hold more than 50000 output tokens
- **THEN** the item fails, and the reason names `output_tokens_limit`

#### Scenario: A run inside the budget
- **WHEN** the model reads two files and then answers with a valid plan
- **THEN** the item is staged

#### Scenario: One item fails and the others are planned
- **WHEN** the plan run of the first of two items spends its budget
- **THEN** the second item is planned, and the job fails at the end for the first item

### Requirement: A toolbox run keeps the return rules of a broken reply
A plan run of the toolbox SHALL send a reply that breaks the schema back to the model once, with the violations. A second reply that breaks the schema SHALL stop the item with the class `StructuredOutputValidationError` and the count of violations. A reply that the checks of the job refuse SHALL go back once, as it does without the toolbox.

#### Scenario: A reply that breaks the schema twice
- **WHEN** both replies of a plan run hold a group with an empty `changes`
- **THEN** the item stops with the class `StructuredOutputValidationError`

#### Scenario: A missing path after the tools
- **WHEN** the first plan of a toolbox run names a path that the commit lacks
- **THEN** the job asks again with the problem, and a second plan with a missing path stops the item

### Requirement: The comment of a staged item reports the plan run
The comment of an item that the toolbox planned SHALL list each tool call of the plan run with the name and the masked, cut argument of the call. It SHALL state the count of model requests, the input tokens and the output tokens. The comment of an item planned without the toolbox SHALL hold none of these lines.

#### Scenario: The comment lists the calls
- **WHEN** the model calls `read_file` for `src/devops_cli/sample.py` and then answers
- **THEN** the comment of the staged item lists `read_file` with that path and the token counts

#### Scenario: An argument with a secret
- **WHEN** a tool call has an argument that looks like a secret
- **THEN** the comment holds the masked text and not the secret
