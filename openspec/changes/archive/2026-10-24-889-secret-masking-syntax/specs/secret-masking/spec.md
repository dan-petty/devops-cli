# Spec Delta

## Purpose

Masks credentials and secret patterns in source code excerpts, configuration files, and telemetry payloads based on syntactic context.

## ADDED Requirements

### Requirement: Syntax-aware secret masking
The secret masking system SHALL evaluate assignments against the syntax of the input text, preserving unquoted code expressions in programming language files and masking assigned credential values in data and configuration files.

#### Scenario: Unquoted expression in code syntax
- **WHEN** secret masking processes an unquoted right-hand side expression such as `password=cfg.db_password` with code syntax
- **THEN** the expression remains unmasked as written

#### Scenario: Dotted identifier in data syntax
- **WHEN** secret masking processes a dotted assignment such as `password=settings.Hunter22` with data syntax
- **THEN** the value is masked with `password=<masked-password>`

#### Scenario: Default masking syntax
- **WHEN** secret masking processes text without an explicit syntax argument
- **THEN** the text is processed using data syntax and credentials are unconditionally masked

### Requirement: Token masking in bracketed boundaries
The secret masking system SHALL detect and mask GitHub tokens, Anthropic API keys, and OpenAI API keys when enclosed in angle brackets, while preserving short documentation placeholders.

#### Scenario: Real token inside angle brackets
- **WHEN** secret masking encounters `<ghs_...>` or `<sk-proj-...>` with valid token length
- **THEN** the token within the brackets is redacted with the corresponding masked token indicator

#### Scenario: Placeholder inside angle brackets
- **WHEN** secret masking encounters a shortened placeholder such as `<ghp_token>`
- **THEN** the text is left unmodified
