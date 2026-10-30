## MODIFIED Requirements

### Requirement: devops config unset removes a key from the config file
`devops config unset <key>` SHALL remove the dotted key and its value from the active config file, and SHALL keep every other line, comment and key of the file. It SHALL load no settings, so it also removes a key that stops the settings from loading. It SHALL copy the file to `<name>.bak-<YYYYMMDD-HHMMSS>` before the change, with the mode of the file, and record the removed key in the audit log. A key name that holds a dot SHALL resolve as one key. Each copy that the command keeps SHALL show the value of each credential that the removal takes out of the file as `***REDACTED***`, and SHALL hold no value of it. This holds for the new copy and for each older retained copy, and for a credential below a removed section. Every other line of a copy SHALL stay as it was. The command SHALL keep the newest 10 copies. A comment line of a copy that holds the value SHALL lose its comment text. A copy SHALL keep its line ends. A copy that is not UTF-8 text, is not YAML, or does not hold a YAML mapping SHALL stop the command with an error that names the copy and quotes no text, before the file changes.

#### Scenario: A key that stops the settings from loading
- **WHEN** the config file holds comments and `ai.vllm_url`, `devops config get ai.provider` fails because of that key, and `devops config unset ai.vllm_url` runs
- **THEN** the command exits 0 and names the file, the line of the key and the copy, the file holds every line as before except the line of `ai.vllm_url`, the copy holds the file as before, and `devops config get ai.provider` exits 0

#### Scenario: A key whose name holds a dot
- **WHEN** the config file holds `ai.gateway_weights` with the keys `qwen3.8:27b` and `gemma4:26b`, and `devops config unset ai.gateway_weights.qwen3.8:27b` runs
- **THEN** the file holds `ai.gateway_weights` with `gemma4:26b` alone

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

#### Scenario: A comment that holds the value
- **WHEN** the config file holds `ai.api_key` with the line comment `# was <value>`, and `devops config unset ai.api_key` runs
- **THEN** the copy holds no `<value>`, and its other comments stay

#### Scenario: A copy with CRLF line ends
- **WHEN** the config file and an older copy have CRLF line ends, and `devops config unset ai.api_key` runs
- **THEN** each copy holds CRLF line ends, and only the credential changed

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
