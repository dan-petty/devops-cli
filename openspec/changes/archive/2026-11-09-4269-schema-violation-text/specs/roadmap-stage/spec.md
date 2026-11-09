## ADDED Requirements

### Requirement: A schema failure names its violations
A plan run of the stage job whose model reply breaks the schema past its retries SHALL fail with an error whose failure line and log line name the count of violations, the stop reason (`validation` or `no tool call`) and at most 3 violations, each with its location, its pydantic error type and its message. Each text SHALL be masked for secrets and cut to 200 characters. The text SHALL NOT hold the input value of a violation.

#### Scenario: Two violations
- **WHEN** a plan reply breaks the schema with two violations, one at `references.0.reason`
- **THEN** the failure text holds `references.0.reason`, its error type, the stop reason and the count 2

#### Scenario: Five violations
- **WHEN** a plan reply breaks the schema with 5 violations
- **THEN** the failure text names 3 of them and the count 5

#### Scenario: A long message
- **WHEN** a violation message has 300 characters
- **THEN** the text holds the first 200 characters of it

#### Scenario: A secret in a message
- **WHEN** a violation message holds a token-shaped secret
- **THEN** the failure text, the log line and the kept file hold the masked value

### Requirement: A schema failure is kept in the refused file
When a plan fails because its reply broke the schema, the stage job SHALL write the stop reason, the count and the texts of the first violations in the field `schema_failure` of the file `<n>.refused.json`, with the replies that the checks refused before it. The staging of the item SHALL delete the file.

#### Scenario: A schema failure
- **WHEN** the plan of item 1 fails with two violations
- **THEN** the file `1.refused.json` holds the stop reason, the count 2 and both violations with their location, type and message

#### Scenario: The item stages later
- **WHEN** the item stages after a schema failure
- **THEN** the file `1.refused.json` is deleted
