## MODIFIED Requirements

### Requirement: A credential keyword and its value sit on one line
The secret masking system SHALL take the value of a credential keyword, or of the separator (`:` or `=`) after it, only from the same line, in data and code syntax. A line break (LF or CR) between the keyword and its separator, or between the keyword or separator and the next word, SHALL end the match. Whitespace that is not a line break, such as a space, a tab or a no-break space, SHALL continue to join a keyword, its separator and its value. The text after a line break SHALL NOT change the result for the line before it.

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

#### Scenario: A credential line before a line that starts with a parenthesis
- **WHEN** secret masking processes the line `api_key: rotation_schedule_monthly_v2` and, on the next line or after a blank line, `(rotated monthly)`
- **THEN** the first line becomes `api_key=<masked-api-key>` and the line `(rotated monthly)` comes back unchanged

#### Scenario: A call on the same line
- **WHEN** secret masking processes `api_key = settings_mod.get_ai_api_key (st)`
- **THEN** the text comes back unchanged
