## ADDED Requirements

### Requirement: A Service log line names the repository of its work
Each JSON line that the roadmap Service writes while a repository reference is current SHALL carry `repo` with the casefolded `owner/name` of that reference, on the router's delivery line and on each line of a round, and `RepoContextFilter` SHALL leave a record unchanged when no reference is current.

#### Scenario: A router delivery record names its repository
- **WHEN** the router handles a signed delivery for `Example-Org/Repo1` and writes its one record through `_Delivery.conclude` in `src/devops_cli/server/routes/webhooks.py` inside the scope of that repository
- **THEN** the JSON line holds `repo` with the value `example-org/repo1`

#### Scenario: A round record names its repository
- **WHEN** a `RepoWorker` round for `Example-Org/Repo1` in `src/devops_cli/server/service.py` writes one record
- **THEN** the JSON line holds `repo` with the value `example-org/repo1`

#### Scenario: A record with no current repository
- **WHEN** a Service logger writes a record that carries no `repo` of its own, with no current reference, through `RepoContextFilter` of `src/devops_cli/telemetry/repo_context.py`
- **THEN** the JSON line has no `repo` key
