## ADDED Requirements

### Requirement: A benchmark names each server by the host and port of its URL
`devops ai benchmark` and the embedding benchmark SHALL name each server by the `host[:port]` text of the httpx2 origin of its URL, as a reply does. The name SHALL show in the output and in every report field that holds a server. It SHALL also show in the saved report and in the setup of the kept run. The benchmark SHALL send the userinfo of the URL as Basic authentication and SHALL write it nowhere. A URL with no origin SHALL show as `unknown`.

#### Scenario: A dry run over two Ollama servers
- **WHEN** a dry run of the chat benchmark has the servers `http://user:pw@example.com:11434` and `http://example.com:11435`
- **THEN** the `Workers:` line is `Workers: 2 (example.com:11434, example.com:11435)`
- **AND** the `server` of each response, peer grade and server summary is `example.com:11434` or `example.com:11435`
- **AND** no output and no report field holds `pw`

#### Scenario: A run against a server with a password
- **WHEN** `devops ai benchmark --servers http://user:pw@example.com:11434` runs a task against that server
- **THEN** the server gets `Authorization: Basic dXNlcjpwdw==` on each request
- **AND** the saved report names the server `example.com:11434`
- **AND** the setup of the kept run lists `example.com:11434`
- **AND** no terminal output, saved file or kept run holds `pw`

#### Scenario: A failed embedding run on a server with a password
- **WHEN** the server `http://user:pw@example.com:11434` answers an embedding request with HTTP 500
- **THEN** the result is failed, and its `server` is `example.com:11434`
- **AND** the server got `Authorization: Basic dXNlcjpwdw==`
- **AND** no output, log line or saved report holds `pw`

#### Scenario: A server URL with no origin
- **WHEN** a benchmark runner gets the server `not-a-url`
- **THEN** the `server` of each result is `unknown`
- **AND** no output and no report field holds `not-a-url`

### Requirement: A benchmark names the endpoint of a model by its host and port
The chat benchmark SHALL name a `model@endpoint` entry `model@host[:port]` in the output and in every report field that holds a model. The embedding benchmark SHALL name the endpoint of the entry by `host[:port]` in the `server` of its results. The setup of the kept run SHALL list the same names. The benchmark SHALL send the userinfo of the endpoint as Basic authentication and SHALL write it nowhere.

#### Scenario: A chat benchmark model with a password in its endpoint
- **WHEN** `devops ai benchmark --models m@http://user:pw@example.com:11434` runs a task
- **THEN** the server gets `Authorization: Basic dXNlcjpwdw==` on each request
- **AND** the terminal output, `models_evaluated`, the `model` of each response and the leaderboard name the model `m@example.com:11434`
- **AND** the saved report and the `setup.models` of the kept run hold `m@example.com:11434`
- **AND** no terminal output, saved file or kept run holds `pw`

#### Scenario: An embedding benchmark with a password in the endpoint
- **WHEN** the embedding benchmark has the model `m@http://user:pw@example.com:11434` and a second server `http://example.com:11435`
- **THEN** the progress lines and the `server` of each result name `example.com:11434` or `example.com:11435`
- **AND** the `setup.models` of the kept run lists `m@example.com:11434`
- **AND** no output, saved report, kept run or log line holds `pw`
