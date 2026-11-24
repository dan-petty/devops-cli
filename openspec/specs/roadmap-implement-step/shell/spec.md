# roadmap-implement-step/shell Specification

## Purpose
The shell tool of an implement step: the programs and the pipes that it admits, the commands that it refuses, the worker bound and the command limit.

## Requirements

### Requirement: The shell of a step takes the worker bound of the process
The shell of a step SHALL get `PYTEST_XDIST_AUTO_NUM_WORKERS` with the value of the process when the process has it, and SHALL not set it otherwise.

#### Scenario: The process has the variable
- **WHEN** the process sets `PYTEST_XDIST_AUTO_NUM_WORKERS` to `2`
- **THEN** the environment of the shell holds the same value

#### Scenario: The process has no variable
- **WHEN** the process does not set it
- **THEN** the environment of the shell does not hold it

### Requirement: The log names no word after a bang
The log line of a shell call whose first word is `!` SHALL name the program `other:<digest>` and SHALL show no word after it.

#### Scenario: A bang command
- **WHEN** the agent calls the shell with `! Authorization: Bearer abcdef0123456789abcdef`
- **THEN** the log line says `program other:` and a digest, and holds no word of the command

### Requirement: The shell of a step waits for its command up to the command limit
The agent of a step SHALL offer the tool `run_command` of the harness as its one shell tool, and no shell tool with a background mode. A call SHALL wait until its command ends, up to `roadmap.implement.command_timeout_seconds`, and the harness SHALL kill a command that runs longer. The step SHALL set the wait of each call to that setting, whatever wait the model gives. The allowlist and the refusals of the shell SHALL apply to the tool.

#### Scenario: The tools of the agent
- **WHEN** a step offers its tools to the model
- **THEN** the tools are `create_directory`, `edit_file`, `grep`, `list_files`, `read_file`, `run_command` and `write_file`

#### Scenario: A wait from the model
- **WHEN** `roadmap.implement.command_timeout_seconds` is 41 and the model calls `run_command` with no wait, and with the waits 5, 99999 and 0
- **THEN** each command reaches the workspace with the wait 41, and the run goes on

### Requirement: The step offers create_directory
The implement step SHALL offer a tool named `create_directory` that creates a directory inside the checkout and refuses a path outside it.

#### Scenario: A directory outside the checkout
- **WHEN** the model calls `create_directory` with `../outside`
- **THEN** the call creates no directory and returns a refusal that names the checkout

### Requirement: The step runs a loopback broker for its shell
A step SHALL run a broker inside the job process on a loopback address and an ephemeral port, through `start_step_broker`, for the length of the step. A start with an address that is not a loopback address MUST raise the roadmap implement error that names the address, and no port SHALL listen then. `stop_step_broker` SHALL close the broker and make its token useless.

#### Scenario: An allowed request reaches the gateway
- **WHEN** A step sends a POST to /chat/completions with the step token to the broker address
- **THEN** The broker sends the same method and path to the configured gateway with the AI key of the job process and returns the gateway answer to the step

#### Scenario: A host that is not loopback is refused
- **WHEN** The step starts the broker with a host that is not a loopback address
- **THEN** The start raises an error that names the address and no port listens

#### Scenario: The token dies with the step
- **WHEN** The step has ended and a request uses the token that the step held
- **THEN** The broker answers a refusal and the recorded gateway receives no request

### Requirement: The broker forwards only the allowed requests
The broker MUST forward only the exact method and path pairs `POST /chat/completions` and `POST /embeddings`, under the path prefix of `ai.gateway_url`, and MUST send each one with `http_client` of `devops_cli.http.entry` at the level of `configured_level`. It MUST refuse every other method or path with no request to the gateway. It MUST add the AI key of the job process upstream, and MUST return no AI key to the caller.

#### Scenario: Another path or method is refused
- **WHEN** A step sends a request to another path, or a method other than POST to an allowed path, with the live step token
- **THEN** The broker answers a refusal and the recorded gateway receives no request

#### Scenario: Another token is refused
- **WHEN** A step sends an allowed request with a token other than the live step token
- **THEN** The broker answers 401 and the recorded gateway receives no request

#### Scenario: The answer holds no AI key
- **WHEN** The gateway answers a request that the broker forwarded
- **THEN** The answer that the step receives holds no value of the AI key of the job process

### Requirement: The shell of a step gets the broker address and the step token
`shell_environment` SHALL give the shell of a step the address of the live broker as `DEVOPS_CLI_BROKER_URL` and its step token as `DEVOPS_CLI_BROKER_TOKEN`, and MUST give it no AI key of the job process. A step whose `ai.provider` is not `gateway`, or whose AI key is absent, SHALL run no broker and SHALL give the shell neither variable.

#### Scenario: The shell gets the broker and the token
- **WHEN** The job starts the shell of a step while the AI key of the job is in the environment of the job process
- **THEN** The environment and the arguments of the shell hold the broker address and the step token, and hold no value of the AI key

#### Scenario: A step without a gateway gets no broker
- **WHEN** The setting ai.provider is not gateway
- **THEN** The step runs no broker and the shell environment holds neither broker variable

### Requirement: The implement agent runs the stock shell with no allowlist
The agent of an implement step SHALL run the `Shell` of `Coder` with no allowed command and no denied command, and SHALL add no capability that refuses a command by a policy of the project. The runner pod SHALL be the sandbox of the step.

#### Scenario: The agent of a step has the stock shell
- **WHEN** The test calls `build_agent` with a sentinel check list.
- **THEN** It finds a `Coder` whose `Shell` holds no allowed command and no denied command, and whose capabilities hold no refusal wrapper.
