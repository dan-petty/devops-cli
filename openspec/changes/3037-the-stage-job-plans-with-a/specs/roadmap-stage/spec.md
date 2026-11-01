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
A plan run of the toolbox SHALL make at most 30 tool calls and use at most 50000 output tokens. The run SHALL offer no tool to a request when fewer than 4 tool calls are left, so the model gives its plan. A run that passes a limit, or that calls a tool that is gone, SHALL fail the item with a reason. The job SHALL plan the other items, and SHALL open no draft pull request for the failed item.

#### Scenario: The tool call limit
- **WHEN** one reply of the model in a plan run holds 31 parallel tool calls
- **THEN** the item fails, and the reason names `tool_calls_limit`

#### Scenario: The tools are gone near the limit
- **WHEN** the model has made 27 tool calls, one in each turn
- **THEN** the next request offers no tool, and a valid plan in the reply stages the item

#### Scenario: A tool call after the tools are gone
- **WHEN** the model calls a tool in a request that offers no tool
- **THEN** the item fails, and the reason names the retry error of that tool

#### Scenario: The output token limit
- **WHEN** the replies of the model in one plan run hold more than 50000 output tokens
- **THEN** the item fails, and the reason names `output_tokens_limit`

#### Scenario: A run inside the budget
- **WHEN** the model reads two files and then answers with a valid plan
- **THEN** the item is staged

#### Scenario: One item fails and the others are planned
- **WHEN** the plan run of the first of two items spends its budget
- **THEN** the second item is planned, and the job fails at the end for the first item

### Requirement: The budget is for each plan run
A plan run SHALL be one model call for a plan. The budget of a plan run SHALL be for that run, not for the item. The planner can make a second plan run for one item, when the checks of the job refuse the first plan. That second run SHALL start with a new budget, so one item can use 60 tool calls and 100000 output tokens at most. The model call that splits the groups of an item SHALL use no tool and SHALL have no tool budget.

#### Scenario: The budget is for each plan run
- **WHEN** the first plan run of an item makes 20 tool calls, the checks refuse its plan, and the second plan run makes 20 tool calls
- **THEN** the second run is inside its own budget, and the item is staged

### Requirement: A toolbox run keeps the return rules of a broken reply
A plan run of the toolbox SHALL send a reply that breaks the schema back to the model once, with the violations. A second reply that breaks the schema SHALL stop the item with the class `StructuredOutputValidationError` and the count of violations. A reply that the checks of the job refuse SHALL go back once, as it does without the toolbox.

#### Scenario: A reply that breaks the schema twice
- **WHEN** both replies of a plan run hold a group with an empty `changes`
- **THEN** the item stops with the class `StructuredOutputValidationError`

#### Scenario: A missing path after the tools
- **WHEN** the first plan of a toolbox run names a path that the commit lacks
- **THEN** the job asks again with the problem, and a second plan with a missing path stops the item

### Requirement: The comment of a staged item reports the plan run
The comment of an item that the toolbox planned SHALL report all plan runs of the item, in the order they ran. It SHALL list each tool call with the name and the masked, cut argument of the call. It SHALL state the count of model requests, the input tokens and the output tokens, summed over all plan runs of the item. The comment of an item planned without the toolbox SHALL hold none of these lines.

#### Scenario: The comment lists the calls
- **WHEN** the model calls `read_file` for `src/devops_cli/sample.py` and then answers
- **THEN** the comment of the staged item lists `read_file` with that path and the token counts

#### Scenario: An item with two plan runs
- **WHEN** the first plan of an item is refused, and the second plan run makes one tool call
- **THEN** the comment lists the tool calls of both runs in order, and its token counts are the sums of both runs

#### Scenario: An argument with a secret
- **WHEN** a tool call has an argument that looks like a secret
- **THEN** the comment holds the masked text and not the secret
