## ADDED Requirements

### Requirement: The domain row refuses a commit that names a configured domain
The table of `devops ci` SHALL hold a row `domain` that runs the `main` of `tests/gate/configured_domain.py`. The row SHALL read `k8s.domain` and `cloudflare.domain` from the config at run time, and each added line and path of each commit from `origin/main` to `HEAD`. It SHALL fail on a line or path that holds a configured domain, in any case, with no letter, digit or hyphen next to it.

#### Scenario: A commit names a configured domain
- **WHEN** `k8s.domain` is `example.net`, and a commit of the branch adds the line `host: api.example.net` as line 2 of `k8s/app.yaml`
- **THEN** the check gives the finding `k8s/app.yaml:2 in commit <sha> names the value of k8s.domain`

#### Scenario: A commit names only example.com
- **WHEN** `k8s.domain` is `example.net`, and the commits of the branch add `example.com`, `notexample.net` and `example.network`, and remove a line that names `api.example.net`
- **THEN** the check gives no finding

#### Scenario: A domain is configured
- **WHEN** the config sets `k8s.domain` to `example.net`, and `devops ci --only domain` runs
- **THEN** the row starts `uv run python -c` with the `main` of `tests.gate.configured_domain`

### Requirement: The domain row never prints the value of a domain
Each finding of the `domain` row SHALL name the path, the line, the commit and the settings key, and no output of the row SHALL hold the value of a domain. A path that names a domain SHALL be named by its commit only.

#### Scenario: The finding of a line holds no value
- **WHEN** `k8s.domain` is `example.net`, and a commit adds the line `host: api.example.net`
- **THEN** the output of the check does not hold `example.net`

#### Scenario: A path names a configured domain
- **WHEN** `cloudflare.domain` is `example.net`, and a commit adds the file `k8s/grafana.example.net.yaml`
- **THEN** the check gives `a path in commit <sha> names the value of cloudflare.domain`, with no path

### Requirement: The domain row is skipped where no domain is configured
When the config sets neither `k8s.domain` nor `cloudflare.domain`, the `domain` row SHALL start no command, SHALL pass, and SHALL show `skipped: <cause>`.

#### Scenario: No domain is configured
- **WHEN** the config sets neither `k8s.domain` nor `cloudflare.domain`, and `devops ci --only domain` runs
- **THEN** the row starts no command, the gate exits 0, and the output shows `[domain] skipped: no k8s.domain or cloudflare.domain is configured, so the row read no commit`

### Requirement: The pre-push hook runs the domain row
The pre-push hook `devops-ci-pre-push` SHALL run the rows `lint`, `format` and `domain` of `devops ci` in check-only mode.

#### Scenario: The hooks of a push
- **WHEN** the hooks of the `pre-push` stage of `.pre-commit-config.yaml` are read
- **THEN** the hook after `branch-current` runs `devops ci --check` with the rows `lint`, `format` and `domain`
