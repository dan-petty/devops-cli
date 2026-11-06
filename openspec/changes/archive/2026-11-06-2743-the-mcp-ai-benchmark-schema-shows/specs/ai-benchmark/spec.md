## ADDED Requirements

### Requirement: The MCP benchmark tool describes models by plain name
The MCP tool `ai_benchmark` SHALL publish a `models` description that gives plain model names only. The description SHALL hold no `model@url` form and no rule for the key or the server of such a form. The example in it SHALL be one that the tool accepts.

#### Scenario: Published description holds no model@url
- **WHEN** a client reads the published schema of `ai_benchmark` and inspects the description of `models`
- **THEN** the description holds no `@`, no `api_base_url`, no `gateway_url` and no word `key`

#### Scenario: The published example is accepted
- **WHEN** the `models` value of a call to `ai_benchmark` is the example that the published description quotes
- **THEN** the refusal check of the tool for a model endpoint passes the value

### Requirement: The benchmark command help keeps model@url
The help text of the option `--models` of `devops ai benchmark` SHALL keep the `model@url` form and the sentence that the MCP tool refuses it, for a person at the command line.

#### Scenario: Command help still shows model@url
- **WHEN** a person reads the help text of `--models` of `devops ai benchmark`
- **THEN** the text holds the example `llama3.1:8b@http://gpu2:11434` and the sentence `The MCP tool refuses a model@url.`
