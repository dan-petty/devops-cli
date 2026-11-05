## ADDED Requirements

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
