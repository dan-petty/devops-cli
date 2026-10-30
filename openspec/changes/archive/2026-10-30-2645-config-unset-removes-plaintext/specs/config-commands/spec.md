## ADDED Requirements

### Requirement: The copies of devops config unset hold no credential value
The copies of the file that `devops config unset` keeps SHALL hold no value of a credential that the removal takes out of the file. A copy shows such a value as `***REDACTED***`, with the key in place. This holds for the new copy, for each older retained copy, and for a credential below a removed section.

#### Scenario: A credential key
- **WHEN** the config file holds `ai.api_key` with the value `FAKE-2645-value` and `ai.model`, and `devops config unset ai.api_key` runs
- **THEN** no file in the directory holds `FAKE-2645-value`, and the new copy holds `ai.api_key` with the value `***REDACTED***` and `ai.model` as before

#### Scenario: A credential in an older copy
- **WHEN** 10 older copies hold `ai.api_key` with a value, and `devops config unset ai.api_key` runs
- **THEN** 10 copies stay, and none holds the value

#### Scenario: A section that holds a credential
- **WHEN** the config file holds `ai.api_key` with a value, and `devops config unset ai` runs
- **THEN** the copy holds `ai.api_key` with the value `***REDACTED***`

#### Scenario: A key that is not a credential
- **WHEN** `devops config unset ai.model` runs
- **THEN** the copy holds the file as it was before the change

### Requirement: The copies of devops config unset keep the rest of the file
A comment line of a copy that holds the value SHALL lose its comment text. Every other line of a copy SHALL stay as it was, with its line ends. A copy SHALL keep the mode of the file, and the command SHALL keep the newest 10 copies.

#### Scenario: A comment that holds the value
- **WHEN** the config file holds `ai.api_key` with the line comment `# was <value>`, and `devops config unset ai.api_key` runs
- **THEN** the copy holds no `<value>`, and its other comments stay

#### Scenario: A copy with CRLF line ends
- **WHEN** the config file and an older copy have CRLF line ends, and `devops config unset ai.api_key` runs
- **THEN** each copy holds CRLF line ends, and only the credential changed

### Requirement: devops config unset stops for a copy that it cannot redact
A copy that is not UTF-8 text, is not YAML, or does not hold a YAML mapping SHALL stop `devops config unset` with an error that names the copy and quotes no text. The command SHALL stop before the config file changes, and SHALL make no new copy.

#### Scenario: A copy that is not a YAML mapping
- **WHEN** an older copy is not UTF-8 text, is not YAML, or is a YAML list or a plain line, and `devops config unset ai.api_key` runs
- **THEN** the command exits 1 with an error that names the copy and quotes no value, the config file stays as it was, and no new copy is made

## RENAMED Requirements

- FROM: `### Requirement: The alert of devops config audit-keys warns about the quotes and the copy`
- TO: `### Requirement: The alert of devops config audit-keys warns about the quotes`

## MODIFIED Requirements

### Requirement: The alert of devops config audit-keys warns about the quotes
The alert SHALL say to quote the file and the key for the shell. It SHALL name no copy of the file to delete, because the removal leaves no copy that holds the value.

#### Scenario: The alert for a leak
- **WHEN** the global config file holds `ai.api_key` with a value and `devops config audit-keys` runs
- **THEN** the alert holds "Quote <file> and <key> for the shell." and names no `.bak-` copy
