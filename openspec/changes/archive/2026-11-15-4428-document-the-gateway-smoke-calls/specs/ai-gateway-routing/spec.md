## ADDED Requirements

### Requirement: One documented call for each hosted group
The LLM Gateway section of `k8s/README.md` SHALL give one chat-completion `curl` call for each hosted group: `claude-sonnet-5-5`, `claude-haiku-5-5`, `gemini-3.8-flash` and `deepseek-v4.1-flash-1017`.

#### Scenario: Each group has its call
- **WHEN** a test reads the smoke section of `k8s/README.md`
- **THEN** each hosted group names one `curl` call to `/v1/chat/completions`

### Requirement: Each call sends only the gateway key
The documented calls SHALL send the gateway master key in `Authorization`, SHALL name the provider key of each group, and SHALL send no provider key in a header.

#### Scenario: The provider key of each group is named
- **WHEN** a test reads the smoke section
- **THEN** the table names `ANTHROPIC_API_KEY` for both Claude groups, `GEMINI_API_KEY` for the Gemini group and `OPENROUTER_API_KEY` for the DeepSeek group

#### Scenario: No provider key reaches the gateway
- **WHEN** a test reads each documented call
- **THEN** each call sends `Authorization: Bearer $KEY` and no header names a provider key

### Requirement: A documented structured call
The smoke section SHALL give one call to `claude-sonnet-5-5` with a `response_format` of type `json_schema` and a schema of a small object.

#### Scenario: The structured call is in the file
- **WHEN** a test reads the smoke section
- **THEN** one call to `claude-sonnet-5-5` holds `response_format` with `json_schema`

### Requirement: The documented run and its record
The smoke section SHALL give the steps that run the five calls after the gateway rolls, record each result and open a fix issue.

#### Scenario: The steps name the record and the fix issue
- **WHEN** a test reads the smoke section
- **THEN** it names the roll onto the new image, a comment on the upgrade issue for each result, and `devops gh issue create --label source/agent` with no priority label
