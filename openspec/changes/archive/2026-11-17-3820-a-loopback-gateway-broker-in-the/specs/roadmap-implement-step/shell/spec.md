## ADDED Requirements

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
