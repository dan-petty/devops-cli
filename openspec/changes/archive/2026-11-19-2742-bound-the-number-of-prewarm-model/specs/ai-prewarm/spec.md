## MODIFIED Requirements

### Requirement: The model label of the prewarm counter is bounded
The label `model` of `devops_cli_ai_prewarms_total` SHALL hold only the characters `A-Z`, `a-z`, `0-9`, `.`, `_`, `:`, `/` and `-`, and SHALL hold at most 128 characters. Each other character SHALL become `_`. The label SHALL hold the model only when it is `ai.model` or a model that a server of the run reports. Each other model SHALL give `other`. The servers of the run are the servers that the run prewarms.

#### Scenario: A model name with symbols
- **WHEN** a server of the run reports the model `my/model`@v2`.0!beta`, and `devops ai prewarm --model 'my/model`@v2`.0!beta'` runs
- **THEN** the counter label `model` is `my/model__v2_.0_beta`

#### Scenario: A long model name
- **WHEN** a server of the run reports a model name of 300 characters, and the run prewarms that model
- **THEN** the counter label `model` has 128 characters

#### Scenario: A normal model name
- **WHEN** the model is `gemma4:26b`, and a server of the run reports it
- **THEN** the counter label `model` is `gemma4:26b`

#### Scenario: A model that no server reports
- **WHEN** a client calls `ai_prewarm` with a `model` that is not `ai.model`, and no server of the run reports it
- **THEN** the counter label `model` is `other`

#### Scenario: The configured model
- **WHEN** the model is `ai.model`, and no server of the run reports it
- **THEN** the counter label `model` is `ai.model`

#### Scenario: A server that gives no model list
- **WHEN** every server of the run fails the request for its models, and the model is not `ai.model`
- **THEN** the counter label `model` is `other` and the run still prewarms the model

#### Scenario: The servers of the run
- **WHEN** a person runs `devops ai prewarm --url http://example.com:11434`, and `ai.ollama_urls` names only `example.org`
- **THEN** the models are requested from `example.com:11434` only

#### Scenario: A provider that is not Ollama
- **WHEN** `ai.provider` is `openai` and `devops ai prewarm` runs
- **THEN** no request for a list of models is sent

## ADDED Requirements

### Requirement: The model attribute of the prewarm span is bounded
The attribute `ai.model` of the span `ai.prewarm` SHALL hold the same text as the label `model` of the counter `devops_cli_ai_prewarms_total` of that run.

#### Scenario: A model that no server reports
- **WHEN** a client calls `ai_prewarm` with a `model` that is not `ai.model`, and no server of the run reports it
- **THEN** the attribute `ai.model` of the span is `other`

#### Scenario: A reported model
- **WHEN** a server of the run reports the model `gemma4:26b`, and the run prewarms it
- **THEN** the attribute `ai.model` of the span is `gemma4:26b`

#### Scenario: A long model name
- **WHEN** a server of the run reports a model name of 300 characters, and the run prewarms that model
- **THEN** the attribute `ai.model` of the span has 128 characters
