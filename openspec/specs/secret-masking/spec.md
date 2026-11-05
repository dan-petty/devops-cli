# secret-masking Specification

## Purpose
Masks credentials and secret patterns in source code excerpts, configuration files, and telemetry payloads based on syntactic context.

## Requirements

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

### Requirement: Token masking in bracketed boundaries
The secret masking system SHALL detect and mask GitHub tokens, Anthropic API keys, and OpenAI API keys when enclosed in angle brackets, while preserving short documentation placeholders.

#### Scenario: Real token inside angle brackets
- **WHEN** secret masking encounters `<ghs_...>` or `<sk-proj-...>` with valid token length
- **THEN** the token within the brackets is redacted with the corresponding masked token indicator

#### Scenario: Placeholder inside angle brackets
- **WHEN** secret masking encounters a shortened placeholder such as `<ghp_token>`
- **THEN** the text is left unmodified

### Requirement: A credential keyword and its value sit on one line
The secret masking system SHALL take the value of a credential keyword, or of the separator (`:` or `=`) after it, only from the same line, in data and code syntax. A line break (LF or CR) between the keyword and its separator, or between the keyword or separator and the next word, SHALL end the match. Whitespace that is not a line break, such as a space, a tab or a no-break space, SHALL continue to join a keyword, its separator and its value.

#### Scenario: A keyword at the end of a line
- **WHEN** secret masking processes the line `$ devops config set ai.api_key` and, on the next line, `ai.api_key is stored in the keyring`, with an LF or a CRLF line break
- **THEN** the two lines come back unchanged

#### Scenario: A separator at the end of a line
- **WHEN** secret masking processes the line `Enter the password:` and, on the next line, `authenticated_user logged in`
- **THEN** the two lines come back unchanged, with the line break between them

#### Scenario: A separator at the start of the next line
- **WHEN** secret masking processes the line `Enter the password` and, on the next line, `: authenticated_user logged in`
- **THEN** the two lines come back unchanged, with the line break between them

#### Scenario: A keyword and its value on one line
- **WHEN** secret masking processes `$ devops config set ai.api_key ai.api_key is stored in the keyring` or `Enter the password: authenticated_user logged in` on one line
- **THEN** the result is `$ devops config set ai.api_key <masked-token> is stored in the keyring` or `Enter the password=<masked-password> logged in`

#### Scenario: A tab or a no-break space between a keyword and its value
- **WHEN** secret masking processes `Enter the password:` and `authenticated_user logged in` on one line, with a tab or a no-break space between them
- **THEN** the result is `Enter the password=<masked-password> logged in`

### Requirement: The next line does not change how a line is masked
The secret masking system SHALL give a line the same result, whatever text comes after the line break (LF or CR) at its end, in data and code syntax. A check after a value reads only the rest of its own line.

#### Scenario: A credential line before a line that starts with a parenthesis
- **WHEN** secret masking processes the line `api_key: rotation_schedule_monthly_v2` and, on the next line or after a blank line, `(rotated monthly)`
- **THEN** the first line becomes `api_key=<masked-api-key>` and the line `(rotated monthly)` comes back unchanged

#### Scenario: A call on the same line
- **WHEN** secret masking processes `api_key = settings_mod.get_ai_api_key (st)`
- **THEN** the text comes back unchanged

### Requirement: A private host name is masked
`mask_private_hosts` SHALL replace each match of `PRIVATE_HOST_PATTERNS` in a text with `<masked-host>`: a name that ends in `.internal`, `.local`, `.lan`, `.corp` or `.home.arpa`, a private or loopback address, and `localhost`. It SHALL leave the rest of the text as it is.

#### Scenario: A host name and an address
- **WHEN** a text holds `https://db.corp.internal/x`, `127.0.0.1` and `localhost`
- **THEN** the result holds `https://<masked-host>/x`, `<masked-host>` and `<masked-host>`, and no other change

#### Scenario: A public host and a code name
- **WHEN** a text holds `example.com`, `198.51.100.7` and `config.local_value`
- **THEN** the result is the text as it was

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

### Requirement: The user name of a URL is masked when the URL has no password
The secret masking system SHALL mask the user name of a URL that has a user name and no password, whatever the scheme. `redact_text` and `mask_secrets` SHALL show `<masked-user>` in place of the user name, in data and code syntax. `mask_uri_credentials` SHALL show `***`. The scheme, the host, the port, the path, the query and the fragment SHALL stay as written.

#### Scenario: A token used as the user name in a text
- **WHEN** secret masking processes `error calling http://tok_0123456789abcdef@example.com:11434/api/embed failed`
- **THEN** the result is `error calling http://<masked-user>@example.com:11434/api/embed failed`

#### Scenario: A harmless user name
- **WHEN** secret masking processes `ssh://git@example.com/org/repo.git`
- **THEN** the result is `ssh://<masked-user>@example.com/org/repo.git`

#### Scenario: A user name in a URL with an IPv6 host, a query and a fragment
- **WHEN** secret masking processes `http://tok123@[2001:db8::1]:11434/x?a=b#c`
- **THEN** the result is `http://<masked-user>@[2001:db8::1]:11434/x?a=b#c`

#### Scenario: One URI with a user name and no password
- **WHEN** `mask_uri_credentials` processes `https://tok_0123456789abcdef@example.com:11434/api/embed`
- **THEN** the result is `https://***@example.com:11434/api/embed`

### Requirement: A URL with no user name stays as written in a text
`redact_text` and `mask_secrets` SHALL leave a URL as written when it has no userinfo, when its user name is empty and it has no password, or when its only `@` is after the authority. `mask_uri_credentials` SHALL fail closed for a text that has an `@` but no userinfo, and SHALL return `<masked-url>`.

#### Scenario: An at sign in a query in a text
- **WHEN** `redact_text` processes `http://example.com:11434/p?email=a@example.com`
- **THEN** the text comes back unchanged

#### Scenario: An empty user name in a text
- **WHEN** `redact_text` processes `http://@example.com/x`
- **THEN** the text comes back unchanged

#### Scenario: An at sign and no userinfo in one URI
- **WHEN** `mask_uri_credentials` processes `http://@example.com/x` or `http://example.com:11434/p?email=a@example.com`
- **THEN** the result is `<masked-url>`

### Requirement: A URL with a user name and a password keeps its masking
The secret masking system SHALL mask both the user name and the password of a URL that has both. `redact_text` SHALL show `<masked-user>:<masked-password>`. `mask_uri_credentials` SHALL keep the user name and show `user:***`. A password with no user name SHALL become `***` in `mask_uri_credentials`.

#### Scenario: A user name and a password in a text
- **WHEN** secret masking processes `http://user:pw12345@example.com/x`
- **THEN** the result is `http://<masked-user>:<masked-password>@example.com/x`

#### Scenario: One URI with a user name and a password
- **WHEN** `mask_uri_credentials` processes `https://user:secret123@example.com:8443/api`
- **THEN** the result is `https://user:***@example.com:8443/api`

#### Scenario: One URI with a password and no user name
- **WHEN** `mask_uri_credentials` processes `http://:supersecretpass@example.com:8080/data`
- **THEN** the result is `http://***@example.com:8080/data`
