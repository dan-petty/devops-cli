## ADDED Requirements

### Requirement: A credential keyword and its value sit on one line
The secret masking system SHALL take the value of a credential keyword, or of the separator (`:` or `=`) after it, only from the same line, in data and code syntax. A line break (LF or CR) between the keyword or separator and the next word SHALL end the match. Whitespace that is not a line break SHALL continue to join a keyword and its value.

#### Scenario: A keyword at the end of a line
- **WHEN** secret masking processes the line `$ devops config set ai.api_key` and, on the next line, `ai.api_key is stored in the keyring`, with an LF or a CRLF line break
- **THEN** the two lines come back unchanged

#### Scenario: A separator at the end of a line
- **WHEN** secret masking processes the line `Enter the password:` and, on the next line, `authenticated_user logged in`
- **THEN** the two lines come back unchanged, with the line break between them

#### Scenario: A keyword and its value on one line
- **WHEN** secret masking processes `$ devops config set ai.api_key ai.api_key is stored in the keyring` or `Enter the password: authenticated_user logged in` on one line
- **THEN** the value after the keyword is masked
