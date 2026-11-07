# crawl4ai-api-token Specification

## Purpose
How the token of the Crawl4AI service reaches the cluster: one managed keyring credential and the two cluster Secret entries that `devops k8s push-secrets` writes from it.

## ADDED Requirements

### Requirement: One keyring value feeds both Secrets
The credential `crawl4ai.api_token` SHALL be stored in the keyring entry `crawl4ai_api_token` and SHALL be read from the variables `DEVOPS_CLI_CRAWL4AI_API_TOKEN` and `CRAWL4AI_API_TOKEN`. The secret table SHALL hold the key `CRAWL4AI_API_TOKEN` of Secret `devops/crawl4ai`, required, and the key `DEVOPS_CLI_CRAWL4AI_API_TOKEN` of Secret `devops/devops-cli`, not required. Both keys SHALL read the keyring entry `crawl4ai_api_token`.

#### Scenario: A test reads the secret table
- **WHEN** a test reads the secret table
- **THEN** both keys name the keyring entry `crawl4ai_api_token`

### Requirement: The push makes the token once
When the keyring and the live Secret hold no value, the push SHALL generate the value of `CRAWL4AI_API_TOKEN` with `token_urlsafe(32)`. The key `DEVOPS_CLI_CRAWL4AI_API_TOKEN` SHALL be adopted from `devops/crawl4ai CRAWL4AI_API_TOKEN`, and SHALL NOT be generated.

#### Scenario: One push makes one token
- **WHEN** the keyring holds no `crawl4ai_api_token` and `devops k8s push-secrets --stack devops` runs
- **THEN** the keyring stores one new value, and both Secrets hold that value

### Requirement: The token is not shown
The token SHALL NOT appear in a command argument, a log line or the output of `devops k8s push-secrets`, with or without `--dry-run`. No tool parameter and no MCP option SHALL take it.

#### Scenario: A push shows no token
- **WHEN** `devops k8s push-secrets --stack devops` runs with and without `--dry-run`
- **THEN** the value, and its base64 form, are in no argument, log record or output

### Requirement: The README lists both rows
The secret table of `k8s/README.md` SHALL list both keys.

#### Scenario: A test reads the README
- **WHEN** a test reads the secret table of `k8s/README.md`
- **THEN** the table holds one row for each key of the secret table
