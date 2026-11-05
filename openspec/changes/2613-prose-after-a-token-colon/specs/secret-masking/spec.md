## ADDED Requirements

### Requirement: A plain word after a credential keyword and a colon is left as written
The secret masking system SHALL leave an unquoted value that follows `token`, `auth_token`, `password`, `passwd` or `pwd` and a colon as written when the value reads as a word, in data and code syntax. A value reads as a word when it has fewer than 24 characters, no digit, no `_`, `-` or `.`, and no capital after its first character. A full stop at the end of the value is not part of the word. An equals sign, or a quote mark before the value, SHALL keep the value masked whatever it looks like.

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

#### Scenario: A plain word after an equals sign or in quotes
- **WHEN** secret masking processes `token=unexpected` or `password: "correcthorse"`
- **THEN** the result is `token=<masked-token>` or `password=<masked-password>`
