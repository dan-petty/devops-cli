## ADDED Requirements

### Requirement: A plain word after a credential keyword and a colon is left as written
The secret masking system SHALL leave a plain word as written when the word is an unquoted value after a colon. The colon follows `token`, `auth_token`, `password`, `passwd` or `pwd`. This holds in data and code syntax. A plain word has fewer than 24 characters. It has no digit, no `_`, `-` or `.`, and no capital after its first character. A full stop at its end is not part of it.

#### Scenario: A registry error that names a token
- **WHEN** secret masking processes `failed to fetch oauth token: unexpected status from GET request to https://ghcr.io/v2/x: 403 Forbidden`
- **THEN** the text comes back unchanged

#### Scenario: A prose word after a password colon
- **WHEN** secret masking processes `wrong password: authentication failed for the account`
- **THEN** the text comes back unchanged

#### Scenario: A word with a leading capital or a full stop
- **WHEN** secret masking processes `failed to refresh token: Unauthorized` or `the reason is the token: unexpected.`
- **THEN** the text comes back unchanged

#### Scenario: A credential after a colon
- **WHEN** secret masking processes `token: abc123def456ghi789` or `password: hunter2hunter2`
- **THEN** the result is `token=<masked-token>` or `password=<masked-password>`

### Requirement: An assignment keeps its value masked
The secret masking system SHALL mask the value of an assignment even when the value reads as a plain word. An assignment uses an equals sign, the operator `:=` or a quote mark before the value. The colon is the only separator that has the exception of a plain word.

#### Scenario: A plain word after an equals sign or in quotes
- **WHEN** secret masking processes `token=unexpected` or `password: "correcthorse"`
- **THEN** the result is `token=<masked-token>` or `password=<masked-password>`

#### Scenario: An assignment operator
- **WHEN** secret masking processes `password:=correcthorse`, `token:=abcdefg` or `token: =correcthorse`
- **THEN** the result is `password=<masked-password>` or `token=<masked-token>`

## MODIFIED Requirements

### Requirement: Syntax-aware secret masking
The secret masking system SHALL evaluate assignments against the syntax of the input text. It SHALL preserve unquoted code expressions in programming language files. It SHALL mask assigned credential values in data and configuration files. One exception exists. The requirement "A plain word after a credential keyword and a colon is left as written" states it.

#### Scenario: Unquoted expression in code syntax
- **WHEN** secret masking processes an unquoted right-hand side expression such as `password=cfg.db_password` with code syntax
- **THEN** the expression remains unmasked as written

#### Scenario: Dotted identifier in data syntax
- **WHEN** secret masking processes a dotted assignment such as `password=settings.Hunter22` with data syntax
- **THEN** the value is masked with `password=<masked-password>`

#### Scenario: Default masking syntax
- **WHEN** secret masking processes text without an explicit syntax argument
- **THEN** the text is processed using data syntax, and the exemption of unquoted code expressions does not apply
