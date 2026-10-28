## ADDED Requirements

### Requirement: The variable of a setting follows its key
A variable SHALL set each declared setting. Its name SHALL be `DEVOPS_CLI_` and the setting's dotted key in upper case, with `_` for `.`, and with `TASK` for the `tasks` segment of `ai.tasks`.

#### Scenario: A plain setting and a task setting
- **WHEN** `DEVOPS_CLI_AI_REFERENCE_MODEL` is `gpt-5` and `DEVOPS_CLI_CLOUDFLARE_ACCESS_BYPASS_IPS` is `192.0.2.1, 198.51.100.0/24`, and the settings load
- **THEN** `ai.reference_model` is `gpt-5` and `cloudflare.access.bypass_ips` is `["192.0.2.1", "198.51.100.0/24"]`

#### Scenario: The variable of a task setting
- **WHEN** the variable of `ai.tasks.chat.provider` is read
- **THEN** it is `DEVOPS_CLI_AI_TASK_CHAT_PROVIDER`

### Requirement: devops config env lists every variable that sets a setting or a credential
`devops config env` and `docs/ENV_VARS.md` SHALL list the variable of every declared setting and of every credential, each with a description.

#### Scenario: The variables that the list missed
- **WHEN** `devops config env` lists its variables
- **THEN** the list holds `DEVOPS_CLI_AI_TASK_CHAT_REASONING_EFFORT`, `DEVOPS_CLI_AI_RAG_TOP_K` and `DEVOPS_CLI_AI_RAG_SCORE_THRESHOLD`, and no listed variable has an empty description

### Requirement: devops config show lists every setting and every credential
`devops config show` SHALL print each declared setting and each credential once, sorted by key. It SHALL print a credential that has a value as `****`, never its value. `--json` SHALL print the rows as a list of objects with `key` and `value`.

#### Scenario: A credential and a setting from the environment
- **WHEN** `DEVOPS_CLI_GRAFANA_TOKEN` and `DEVOPS_CLI_AI_MODEL` are set, and `devops config show --json` runs
- **THEN** the row of `grafana.token` has the value `****`, the row of `ai.model` has the value of the variable, and the output does not hold the token
