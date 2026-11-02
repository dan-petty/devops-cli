## MODIFIED Requirements

### Requirement: Hosted groups join no pool
No pool, context-window fallback or routing group of the gateway config SHALL name a hosted group, and no fallback SHALL send a group that is not hosted to a hosted group, so a prompt leaves the cluster for a provider only when its caller names a hosted group. A fallback from one hosted group to another hosted group MAY exist.

#### Scenario: A fallback to a hosted group
- **WHEN** a fallback chain sends `devops-review` to `claude-haiku-5-5`
- **THEN** the hosted-group check fails

#### Scenario: A failed Sonnet call
- **WHEN** a call to `claude-sonnet-5-5` fails
- **THEN** the gateway answers it with `deepseek-v4.1-flash-1017`
