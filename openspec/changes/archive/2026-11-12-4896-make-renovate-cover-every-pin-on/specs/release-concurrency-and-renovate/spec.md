## MODIFIED Requirements

### Requirement: Renovate manages Terraform, devcontainers, pre-commit, and action digests under taxonomy labels
The shared preset `.github/renovate/base.json` SHALL label each update `type/chore` and `scope/deps`, add `scope/ci` to github-actions, pre-commit and devcontainer updates, add `scope/infra` to dockerfile, docker-compose, kubernetes, argocd, helm-values and terraform updates, pin the digests of github-actions and dockerfile, and turn the pre-commit manager on. Each label SHALL exist in `.github/labels.yml` or in the workflow labels.

#### Scenario: The Renovate configuration is read
- **WHEN** a test reads `.github/renovate/base.json` and `.github/renovate.json`
- **THEN** the preset labels are `type/chore` and `scope/deps`, and its add-label rules name the CI and infra managers
- **AND** every label of both files is in `.github/labels.yml` or the workflow labels

### Requirement: Renovate sets no minimum release age
`.github/renovate/base.json` and `.github/renovate.json` SHALL hold no `minimumReleaseAge`, and the preset SHALL extend only `config:recommended`, so that Renovate opens the pull request for a release with a security fix or a bug fix on the day it is published.

#### Scenario: The Renovate configuration is read
- **WHEN** a test reads both Renovate files
- **THEN** neither text holds `minimumReleaseAge`
- **AND** the `extends` list of the preset is `["config:recommended"]`, and the repository config extends only the preset

## ADDED Requirements

### Requirement: Renovate updates on a fixed schedule within the CI cap
The preset SHALL use the time zone UTC and the schedule Monday, give a patch update the schedule `at any time` in its own branch, group the non-major updates of each ecosystem, open at most 2 pull requests an hour and keep at most 8 open, push an open pull request again only on a conflict (`rebaseWhen: conflicted`), and run lock file maintenance on Monday.

#### Scenario: The schedule and the limits are read
- **WHEN** a test reads `.github/renovate/base.json`
- **THEN** `schedule` is `["* * * * 1"]`, the only patch rule sets `["at any time"]`, `prHourlyLimit` is 2, `prConcurrentLimit` is 8 and `rebaseWhen` is `conflicted`
- **AND** each ecosystem group matches only minor and patch updates

### Requirement: Renovate proposes a security fix at once
The preset SHALL turn on OSV alerts and give an alert pull request the labels `type/security` and `scope/deps`, the prefix `fix(deps):`, at most 4 open, and the newest fixed release. The Dependency Dashboard SHALL list unresolved CVEs and abandoned packages. A Python minor or major, and a major of Node, PostgreSQL or Mattermost, SHALL wait for an approval on the Dashboard.

#### Scenario: The security settings are read
- **WHEN** a test reads `.github/renovate/base.json`
- **THEN** `osvVulnerabilityAlerts` is true and `vulnerabilityAlerts.vulnerabilityFixStrategy` is `highest`
- **AND** the only approval rules match `python` minor and major updates, and the `node`, PostgreSQL and Mattermost majors

### Requirement: Every pin of the repository has a Renovate manager
No rule SHALL turn off a manager. Each pinned file SHALL match a file pattern of its manager. Custom managers SHALL read the pins that no built-in manager reads: the Python minor, the runner tools table, the tools lock, CloudNativePG and Mattermost images, values tags with no repository and Grafana plugins. Pins that a test compares SHALL share one group of every update type.

#### Scenario: The managers are read against the tracked files
- **WHEN** a test applies the file patterns and the match strings of the configuration to the tracked files
- **THEN** each pinned file matches its manager, and the custom managers find exactly the expected pins
- **AND** the coupled groups `trivy`, `argo`, `cloudflared`, `uv`, `gh`, `node`, `python runtime`, `ruff`, `bandit`, `actionlint`, `openspec` and `dcgm-exporter` set no update type

### Requirement: Renovate titles fit the semantic title check
The preset SHALL write each title as `chore(deps): update <dependency> to <version>`, name an action without the word `action`, name a devcontainer feature by the last part of its reference, and add no `[SECURITY]` suffix, so that each summary has at most 60 characters.

#### Scenario: A title is built for each pinned dependency
- **WHEN** a test builds the summary of an update for each dependency that the repository pins, and for each group
- **THEN** no summary has more than 60 characters
