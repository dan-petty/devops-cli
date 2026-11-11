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
