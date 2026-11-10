# ai-ask-jev Specification

## Purpose
The command `devops ai ask-jev` and the MCP tool `ai_ask_jev` send one typed question to TypeSafe Jev and return the answer with its probability. The skill `ask-jev` tells an agent when to ask. A Jev answer is evidence, not a verdict.

## Requirements

### Requirement: The command asks one question and prints the typed answer
`devops ai ask-jev <kind> <question>` SHALL send one System One request with one question of the kind `choice`, `noul` or `score`, and SHALL print the answer, its probability, the probability of each option or level, and the token count. With `--json` it SHALL print the typed result as JSON.

#### Scenario: A choice
- **WHEN** Jev answers a choice question with the option `bug` at probability 0.91
- **THEN** the output holds `Answer: bug`, `Probability: 0.91` and the token count, and the exit code is 0

#### Scenario: A yes/no as JSON
- **WHEN** the command runs with `--json` and Jev answers 0.83
- **THEN** the output is JSON with the answer `yes` and the probability 0.83

### Requirement: The command refuses an input that Jev must not get
The command SHALL exit non-zero, name the rule, quote no input and send no request when the question is empty, when an option or level does not belong to the kind, when the number of options or levels is out of bounds, when the input is larger than `CONST_AI_JEV_ASK_MAX_INPUT_CHARS` characters, or when the input holds a secret.

#### Scenario: A secret in the input
- **WHEN** the question holds a GitHub token
- **THEN** the exit code is not 0, the output says that Jev is a hosted model, and the gateway gets no request

#### Scenario: An input that is too large
- **WHEN** the question is longer than the bound
- **THEN** the exit code is not 0 and the gateway gets no request

### Requirement: A failed call exits non-zero
The command SHALL exit non-zero, and print neither the key nor the input, when the gateway answers an error, does not answer, or answers a reply that does not match the question.

#### Scenario: The gateway answers 404
- **WHEN** the gateway answers HTTP 404
- **THEN** the exit code is not 0 and the output says that the gateway did not answer

### Requirement: A dry run sends no request
`devops ai ask-jev --dry-run` SHALL make no request. It SHALL check the input as the real run does, and print the request with the key as a placeholder.

#### Scenario: A dry run
- **WHEN** the command runs with `--dry-run`
- **THEN** the output holds `POST` and the `/v1/systemone` address and the placeholder for the key, and the gateway gets no request

### Requirement: The MCP tool is generated from the command and is read-only
The server SHALL publish the tool `ai_ask_jev` with `readOnlyHint` true, in the `ai` domain. Its schema SHALL hold no `format` or `json` property, and its input SHALL meet the same bounds as the command.

#### Scenario: The tool schema
- **WHEN** a client lists the tools
- **THEN** `ai_ask_jev` is read-only and its schema names the properties `kind`, `question`, `context`, `option`, `level`, `yes`, `no` and `dry_run`

### Requirement: The skill tells an agent when to ask Jev
The skill `ask-jev` SHALL name the command and the tool, say when to ask and when not to ask, say that a secret never goes to Jev, and say that a Jev answer is evidence and not a verdict. It SHALL exist with the same text in `.claude/skills`, `.agents/skills` and `.kilocode/skills`.

#### Scenario: The skill roots are compared
- **WHEN** the invariant test reads the skill in the three roots
- **THEN** the texts are equal and name `devops ai ask-jev` and `ai_ask_jev`
