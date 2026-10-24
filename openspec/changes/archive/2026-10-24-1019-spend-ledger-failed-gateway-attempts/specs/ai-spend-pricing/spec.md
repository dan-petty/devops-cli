## ADDED Requirements

### Requirement: Each HTTP attempt that reaches the gateway and fails is recorded in the spend ledger
devops-cli SHALL record each HTTP attempt that reaches the gateway and fails with finish reason `error`, the attempt's wall duration, 0 prompt and 0 completion tokens unless the provider reported usage, and the serving backend and deployment model when the error response names them. A connection that never opens SHALL NOT write a row.

#### Scenario: A gateway request fails with HTTP 500 before succeeding
- **WHEN** a chat dispatch request receives HTTP 500 on its first attempt and succeeds with HTTP 200 on its second attempt
- **THEN** two rows are recorded in the spend ledger: the first with finish reason `error` and 0 tokens, and the second with finish reason `stop`

#### Scenario: A gateway request times out waiting for response
- **WHEN** a chat dispatch request encounters a read timeout on its first attempt and succeeds on its second attempt
- **THEN** two rows are recorded in the spend ledger: the first with finish reason `error`, and the second with finish reason `stop`

#### Scenario: A connection failure writes no row
- **WHEN** a chat dispatch request encounters a connection error on its first attempt and succeeds on its second attempt
- **THEN** exactly one row is recorded in the spend ledger with finish reason `stop`

### Requirement: A successful reply takes the served model from the reply body when headers omit it
When a gateway reply contains a model in its reply body that differs from the requested model alias, and the gateway response headers omit `x-litellm-model-name`, devops-cli SHALL record the resolved model in `served_model`.

#### Scenario: A gateway reply with model in reply body
- **WHEN** a request for alias `devops-review` receives a reply with body model `gpt-oss:20b` and a serving backend header
- **THEN** the spend-ledger row records model `devops-review`, served_by with the backend header value, and served_model `gpt-oss:20b`
