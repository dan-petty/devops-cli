## ADDED Requirements

### Requirement: A closing quote mark stays when no quote mark opened the value
The secret masking system SHALL end the match of an assigned credential value before a quote mark when no quote mark opened the value, and SHALL leave that quote mark in the text. This holds for the rules of `token`, `auth_token`, `password`, `passwd`, `pwd`, `client_secret` and `aws_secret_access_key`, in data and code syntax. So the text of a JSON reply is still valid JSON after the mask replaces a secret inside one of its strings.

#### Scenario: A token in the query of a URL in a JSON string
- **WHEN** secret masking processes `{"download_url":"https://example.com/o/r/f.txt?token=AGJ4EXAMPLE1234567890","type":"file"}`
- **THEN** the result is `{"download_url":"https://example.com/o/r/f.txt?token=<masked-token>","type":"file"}`, and `json.loads` parses it

#### Scenario: Another credential keyword in the query of a URL in a JSON string
- **WHEN** secret masking processes a JSON string with `?password=hunter2hunter2`, `?client_secret=abcdefghij0123456789abcdefghij` or `?aws_secret_access_key=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA` (40 letters)
- **THEN** the value becomes `password=<masked-password>`, `client_secret=<masked-client-secret>` or `aws_secret_access_key=<masked-aws-secret>`, the quote mark that closes the string stays, and `json.loads` parses the text

#### Scenario: A string in single quote marks
- **WHEN** secret masking processes `{'download_url':'https://example.com/f?token=AGJ4EXAMPLE1234567890','type':'file'}`
- **THEN** the result is `{'download_url':'https://example.com/f?token=<masked-token>','type':'file'}`

#### Scenario: A value with no quote mark
- **WHEN** secret masking processes `https://example.com/f?token=AGJ4EXAMPLE1234567890` or `token=AGJ4EXAMPLE1234567890 next`
- **THEN** the result is `https://example.com/f?token=<masked-token>` or `token=<masked-token> next`

#### Scenario: The reply of devops gh api
- **WHEN** `devops gh api repos/octo/private/contents/f.txt` prints a reply whose `download_url` holds `?token=AGJ4EXAMPLE1234567890`
- **THEN** the printed text parses as JSON, and its `download_url` ends with `?token=<masked-token>`

### Requirement: A value in a pair of quote marks is masked with the pair
The secret masking system SHALL mask a credential value that a quote mark opened together with its opening quote mark and its closing quote mark of the same kind, for the rules of the requirement above. A closing quote mark of the other kind SHALL stay in the text.

#### Scenario: A value in a pair of quote marks
- **WHEN** secret masking processes `token="AGJ4EXAMPLE1234567890" next` or `{"note": "set token='AGJ4EXAMPLE1234567890' now"}`
- **THEN** the result is `token=<masked-token> next` or `{"note": "set token=<masked-token> now"}`

#### Scenario: A closing quote mark of the other kind
- **WHEN** secret masking processes `token='AGJ4EXAMPLE1234567890" next`
- **THEN** the result is `token=<masked-token>" next`
