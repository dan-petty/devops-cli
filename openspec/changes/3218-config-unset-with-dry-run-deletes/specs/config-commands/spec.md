## MODIFIED Requirements

### Requirement: devops config unset --dry-run writes nothing
`devops --dry-run config unset <key>` SHALL print the dry-run response with the file, the key, its line and the lines of the unified diff of the removal, SHALL write no file, no backup and no audit record, and SHALL show `***REDACTED***` in place of the value of each credential path of `write_history.credential_paths`.

#### Scenario: A dry run of a removal
- **WHEN** `devops --dry-run config unset ai.vllm_url` runs and the config file holds `ai.vllm_url` on line 7
- **THEN** the command exits 0, the dry-run response holds the key, the line 7 and the diff lines `@@ -7 +6,0 @@` and `-  vllm_url: <value>`, and the file, its directory and the audit log do not change

#### Scenario: A dry run of a credential removal
- **WHEN** `devops --dry-run config unset ai.api_key` runs and the config file holds a credential key on line 4
- **THEN** the output holds `***REDACTED***`, holds no value of that key, and the config file and its directory are unchanged

#### Scenario: A dry run of a credential that a comment line also holds
- **WHEN** `devops --dry-run config unset ai.api_key` runs and a comment line of the config file holds the value of that key
- **THEN** no line of the diff holds the value, also not as a comment line, and the config file and its directory are unchanged
