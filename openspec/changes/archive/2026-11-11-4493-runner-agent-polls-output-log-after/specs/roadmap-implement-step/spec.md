## MODIFIED Requirements

### Requirement: The implement prompt forbids polling
The implement prompt SHALL state that a call of the tool `run_command` waits until its command ends, up to `roadmap.implement.command_timeout_seconds` with the default of that setting, and MUST forbid polling with `sleep`, `time.sleep` or a repeated `tail`. It MUST NOT state that a shell call returns when its command ends with no limit.

#### Scenario: The prompt holds the no-poll rule
- **WHEN** A test reads `src/devops_cli/ai/tasks/roadmap_implement_step.md`
- **THEN** The rule names `run_command`, the wait until the command ends, the setting with its default, and sleep, time.sleep and a repeated tail as forbidden, and the prompt holds no "270"

### Requirement: A shell call in a trace holds its exit status
The `tool` event of a `run_command` call SHALL hold `status`, the exit code of the command, and no text of its output: the code of the last line `[exit code: <n>]`, else 0. A call whose command ran past its wait, a refused call and a call of another tool SHALL hold no `status`.

#### Scenario: The exit status of a shell call
- **WHEN** the result of a `run_command` call ends with the line `[exit code: 128]`
- **THEN** the `tool` event holds `status` 128 and no text of the output

#### Scenario: A command that exits with 0
- **WHEN** the result of a `run_command` call has no line of an exit code
- **THEN** the `tool` event holds `status` 0

#### Scenario: A shell call with no status
- **WHEN** the result of a `run_command` call ends with the line of the timeout
- **THEN** the `tool` event holds no `status`

### Requirement: A run that reaches a limit ends stopped
`UsageLimits` SHALL cap a run, extra turn included, at `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` requests and `CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS` tool calls. A run that reaches a limit, exceeds the retries of a tool, or has more than `CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS` shell refusals in the step, SHALL end as stopped, and the step SHALL reset the checkout. The reason SHALL hold the class and the `message` of the error, masked and cut to `CONST_ROADMAP_RUN_ERROR_CHARS` characters.

#### Scenario: A model that never ends
- **WHEN** the model calls a tool in every reply
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: ` and holds the message of the error, the model got `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` requests at most, and the checkout is reset

#### Scenario: A model that calls too many tools
- **WHEN** the model calls more tools than `CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS` before it reaches the request limit
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: `, and the checkout is reset

#### Scenario: The tools of the agent
- **WHEN** the step makes its first request
- **THEN** the function tools offered are `edit_file`, `grep`, `list_files`, `read_file`, `run_command` and `write_file`, and no `delegate_task`

#### Scenario: The extra turn shares the budget
- **WHEN** the first turn used all but one of the model requests and the extra turn needs two
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: `, and the model got `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` requests at most over both turns

#### Scenario: A model that keeps calling a refused program
- **WHEN** the model calls the shell tool with `pytest tests/test_sample.py` in every reply
- **THEN** the model gets `CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS` refusals as tool results, the next call ends the run, the step reports stopped with a reason that starts with `UnexpectedModelBehavior: Too many commands refused by policy in one step: the limit is` and the limit, and the checkout is reset

#### Scenario: The stop of the refusal limit is a refused tool
- **WHEN** the step stops because the shell refused more commands than the limit
- **THEN** the failure class of the reason is `refused_tool`

#### Scenario: A secret in the message of the error
- **WHEN** the message of the pydantic-ai error holds a token in the form of a GitHub token
- **THEN** the reason holds the mask in place of the token

#### Scenario: A long message of the error
- **WHEN** the message of the pydantic-ai error is longer than `CONST_ROADMAP_RUN_ERROR_CHARS` characters
- **THEN** the message in the reason is cut to that length, and the counts of the next requirement are still in the reason

#### Scenario: The body of the error
- **WHEN** the pydantic-ai error has the message `The reply broke the rules.` and the body `MODEL-TEXT`
- **THEN** the reason is `UnexpectedModelBehavior: The reply broke the rules.`, with no `MODEL-TEXT`

### Requirement: A call with a command writes the command to the Job log before it runs
Before a call that has a `command` runs, the agent SHALL write the line `Tool call: <tool>, started: <command>`. The command SHALL be the first word and at most `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS` words, escaped and cut to `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS` characters. The line SHALL hide each secret, the value of each `name=value` word that is not a number, and each word with a space. When the first word is no known program, the command SHALL be `other`.

#### Scenario: A refused program
- **WHEN** the model calls `run_command` with `pytest tests/test_sample.py`, and then ends its run
- **THEN** the standard error stream holds the lines "Tool call: run_command, started: pytest tests/test_sample.py" and "Tool call: run_command, program pytest, refused."

#### Scenario: The line comes before the call
- **WHEN** the model calls `run_command` with `uv run pytest -n 48`, and the tool is still running
- **THEN** the standard error stream holds the line "Tool call: run_command, started: uv run pytest -n 48" and no line with an outcome

#### Scenario: A long command
- **WHEN** the command has more words than `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_WORDS`, or more characters than `CONST_ROADMAP_IMPLEMENT_LOG_COMMAND_CHARS`
- **THEN** the line holds the first words, cut, and ends with " ..."

#### Scenario: A secret in an argument
- **WHEN** the command is `git remote add origin https://user:ghp_<token>@example.com/x.git`, with a GitHub token in place of `<token>`
- **THEN** the line holds no part of the token

#### Scenario: A value after a name
- **WHEN** an argument has the form `name=value` and the value is not a number, for example `ai.api_key=<value>` or `http.extraheader=AUTHORIZATION: basic <value>`
- **THEN** the line holds the name and the word `<masked>` in place of the value, and an argument with a number as the value, such as `--numprocesses=48`, stays as it is

#### Scenario: Free text in an argument
- **WHEN** an argument holds a space, as the message of a commit does
- **THEN** the line holds the word `<masked>` in place of the argument

#### Scenario: A control character in an argument
- **WHEN** an argument holds an escape sequence or another control character that is no space
- **THEN** the line is one line, and it holds the escaped form of the character

#### Scenario: A first word that is no program
- **WHEN** the first word of a shell command is an assignment such as `API_KEY=hunter2`, a path, a word with a space or a quote, an escape sequence, or the command has an unclosed quote
- **THEN** the lines hold "started: other" and "program other" and hold no part of the command

## ADDED Requirements

### Requirement: The shell of a step waits for its command up to the command limit
The agent of a step SHALL offer the tool `run_command` of the harness as its one shell tool, and no shell tool with a background mode. A call SHALL wait until its command ends, up to `roadmap.implement.command_timeout_seconds`, and the harness SHALL kill a command that runs longer. The step SHALL set the wait of each call to that setting, whatever wait the model gives. The allowlist and the refusals of the shell SHALL apply to the tool.

#### Scenario: The tools of the agent
- **WHEN** a step offers its tools to the model
- **THEN** the tools are `edit_file`, `grep`, `list_files`, `read_file`, `run_command` and `write_file`

#### Scenario: A wait from the model
- **WHEN** `roadmap.implement.command_timeout_seconds` is 41 and the model calls `run_command` with no wait, and with the waits 5, 99999 and 0
- **THEN** each command reaches the workspace with the wait 41, and the run goes on

### Requirement: The operator refusal names the code of python -c
The hint of a refusal for an operator SHALL state that a `;`, a new line or a heredoc in the code of `python -c` is refused too. It SHALL tell the agent to write that code to a file under `.data/agent/scratch/` and to run `uv run python <file>`.

#### Scenario: A new line in the code of python -c
- **WHEN** the model calls `run_command` with `uv run python -c` and code that holds a new line
- **THEN** the refusal names the operator, states the rule of one command in each call, and holds the hint about the code of `python -c` and the script file

### Requirement: The implement prompt gives the count of extra turns
The implement prompt SHALL state that a step has at most `roadmap.implement.repair_rounds` extra turns, with the default of that setting, and that each failed check or hook takes one. It MUST NOT promise one more turn for an error of `ruff check` or `mypy`.

#### Scenario: The prompt names the setting of the extra turns
- **WHEN** A test reads `src/devops_cli/ai/tasks/roadmap_implement_step.md`
- **THEN** The prompt names `roadmap.implement.repair_rounds` with its default and holds no promise of one more turn

### Requirement: The implement prompt names the refusal of a heredoc
The implement prompt SHALL state that the shell refuses a new line, a heredoc, and code of `python -c` that holds a `;` or a new line. It SHALL tell the agent to write that code to a file under `.data/agent/scratch/` and to run `uv run python <file>`. The rule SHALL win over the base instructions of `Coder`, which tell the agent to use a heredoc.

#### Scenario: The prompt names the heredoc before the first call
- **WHEN** A test reads `src/devops_cli/ai/tasks/roadmap_implement_step.md`
- **THEN** The prompt names a heredoc, `python -c`, a new line, a `;`, `.data/agent/scratch/` and `uv run python <file>`, and the shell refuses a new line and a `;`
