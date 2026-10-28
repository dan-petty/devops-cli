# ai-structured-reply-constraint Specification

## Purpose
Which constraint each provider gets for a structured reply of `chat_structured`, in which form, and which provider keeps the schema in the system message only.

## Requirements

### Requirement: An OpenAI model gets the response format of its pydantic-ai profile
Inside a structured reply, the `openai` provider SHALL send `response_format` with `type` `json_schema`, the schema's name, the schema as the profile's transformer returns it, and `strict` set to whether the schema fits OpenAI's strict mode, when the model's pydantic-ai profile supports JSON-schema output.

#### Scenario: A refinement proposal to an OpenAI model
- **WHEN** `chat_structured` asks an `openai` model for a `RefinementProposal`
- **THEN** the request has `response_format` `{"type": "json_schema", "json_schema": {"name": "RefinementProposal", "schema": <the schema as OpenAIJsonSchemaTransformer with strict unset returns it>, "strict": false}}`

### Requirement: A Claude model gets the output format of its pydantic-ai profile
Inside a structured reply, the `claude` provider SHALL send `output_config.format` with `type` `json_schema` and the schema as `AnthropicJsonSchemaTransformer` with `strict` true returns it, when the model's pydantic-ai profile supports JSON-schema output, and SHALL keep the `effort` of adaptive thinking in the same `output_config`. A model that the profile does not name SHALL get no format.

#### Scenario: A model that supports JSON-schema output
- **WHEN** `chat_structured` asks `claude-sonnet-4-6` for a `RefinementProposal` without thinking
- **THEN** the request's `output_config` is `{"format": {"type": "json_schema", "schema": <the transformed schema>}}`

#### Scenario: The same model with adaptive thinking
- **WHEN** `chat_structured` asks `claude-sonnet-4-6` for a `RefinementProposal` with thinking, and the model supports adaptive thinking
- **THEN** the request's `output_config` holds `effort` `medium` and the same `format`

#### Scenario: A model that the profile does not name
- **WHEN** `chat_structured` asks `claude-example-1` for a `RefinementProposal`
- **THEN** the request has no `output_config`

### Requirement: Copilot keeps the schema in the system message only
Inside a structured reply, the `copilot` provider SHALL send no `response_format`.

#### Scenario: A refinement proposal through Copilot
- **WHEN** `chat_structured` asks the `copilot` provider for a `RefinementProposal`
- **THEN** the request ends its system message with the schema and has no `response_format`
