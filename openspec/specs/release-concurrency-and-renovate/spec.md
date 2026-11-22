# release-concurrency-and-renovate Specification

## Purpose
Isolate release workflow concurrency runs per branch reference, and configure Renovate, through a shared preset, to update every pin of the Service repositories on a fixed schedule, with security fixes at once, limits for the CI cap, taxonomy labels and titles that pass the semantic title check.

## Requirements

### Requirement: The release workflow isolates concurrency per branch
`.github/workflows/release.yml` SHALL configure its concurrency block with `group: release-${{ github.ref }}` and `cancel-in-progress: false`, so that release runs on separate branch references do not block or cancel one another.

#### Scenario: The release workflow manifest is read
- **WHEN** `.github/workflows/release.yml` is parsed as a workflow mapping
- **THEN** its `concurrency` property equals `{"group": "release-${{ github.ref }}", "cancel-in-progress": false}`

### Requirement: Renovate manages Terraform, devcontainers, pre-commit, and action digests under taxonomy labels
The shared preset `github>dan-petty/infra//renovate/base` SHALL label each update `type/chore` and `scope/deps`, add `scope/ci` to github-actions, pre-commit and devcontainer updates, add `scope/infra` to dockerfile, docker-compose, kubernetes, argocd, helm-values and terraform updates, pin the digests of github-actions and dockerfile, and turn the pre-commit manager on. Each label SHALL exist in `.github/labels.yml` or in the workflow labels.

#### Scenario: The Renovate configuration is read
- **WHEN** Renovate opens a pull request in devops-cli that updates an action, and a person runs `devops gh api repos/dan-petty/devops-cli/issues/<number> --jq '[.labels[].name]'`
- **THEN** the labels are `type/chore`, `scope/deps` and `scope/ci`
- **AND** each label is in `.github/labels.yml` or in the workflow labels of `src/devops_cli/roadmap/workflow_labels.py`

#### Scenario: An update of a chart
- **WHEN** Renovate opens a pull request in devops-cli that moves the chart of an Argo CD Application under `k8s/argocd/apps/`
- **THEN** the labels of the pull request are `type/chore`, `scope/deps` and `scope/infra`

### Requirement: Renovate sets no minimum release age
`.github/renovate.json` and the shared preset `github>dan-petty/infra//renovate/base` SHALL hold no `minimumReleaseAge`. The preset SHALL extend only `config:recommended`, and `.github/renovate.json` SHALL extend only the preset, so that Renovate opens the pull request for a release with a security fix or a bug fix on the day it is published.

#### Scenario: The Renovate configuration is read
- **WHEN** a person runs `npx --yes --package renovate@44.239.2 -- renovate-config-validator --strict --no-global .github/renovate.json`
- **THEN** the command exits 0

#### Scenario: A patch release on the day it is published
- **WHEN** a dependency that devops-cli pins publishes a patch release, and the next run of CronJob `renovate` ends
- **THEN** Renovate has opened the pull request of the patch, or the Dependency Dashboard issue lists the patch as held by the hourly or the concurrent limit
- **AND** no Renovate pull request or Dashboard line holds the update for a release age

### Requirement: Renovate updates on a fixed schedule within the CI cap
The shared preset `github>dan-petty/infra//renovate/base` SHALL use the time zone UTC and the schedule Monday, give a patch update the schedule `at any time` in its own branch, group the non-major updates of each ecosystem, open at most 2 pull requests an hour and keep at most 8 open, not push an open branch again only because `main` moved (`rebaseWhen: conflicted`), push an open branch only in the schedule of that branch (`updateNotScheduled: false`), and run lock file maintenance on Monday.

#### Scenario: A minor release outside the schedule
- **WHEN** a dependency of an ecosystem group of devops-cli publishes a minor release on a day that is not Monday (UTC), and a person reads the Dependency Dashboard issue of devops-cli after the next run of CronJob `renovate`
- **THEN** the Dashboard lists the group as awaiting its schedule, and no open Renovate pull request holds the minor release

#### Scenario: The schedule and the limits are read
- **WHEN** a person runs `devops gh api 'repos/dan-petty/devops-cli/pulls?state=open&per_page=100' --jq '[.[] | select(.user.login == "dan-petty-renovate[bot]" and ([.labels[].name] | index("type/security") | not))] | length'`
- **THEN** the number is at most 8

### Requirement: Renovate proposes a security fix at once
The shared preset `github>dan-petty/infra//renovate/base` SHALL turn on OSV alerts and give an alert pull request the labels `type/security` and `scope/deps`, the prefix `fix(deps):`, at most 4 open, and the newest fixed release. The Dependency Dashboard SHALL list unresolved CVEs and abandoned packages. A Python minor or major, and a major of Node, PostgreSQL or Mattermost, SHALL wait for an approval on the Dashboard.

#### Scenario: The security settings are read
- **WHEN** OSV publishes an advisory with a fixed release for a dependency that devops-cli pins, and the next run of CronJob `renovate` ends
- **THEN** Renovate has opened a pull request that moves the dependency to the newest fixed release, with the labels `type/security` and `scope/deps` and the title prefix `fix(deps):`

#### Scenario: A new Python minor
- **WHEN** Python publishes a new minor, and the next run of CronJob `renovate` ends
- **THEN** the Dependency Dashboard issue of devops-cli lists the minor for an approval, and no Renovate pull request moves the Python minor

### Requirement: Every pin of the repository has a Renovate manager
No rule SHALL turn off a manager. Each pinned file SHALL match a file pattern of its manager. Custom managers SHALL read the pins that no built-in manager reads: the Python minor, CloudNativePG and Mattermost images, values tags with no repository and Grafana plugins. No custom manager SHALL write a tool version into a file under `src/`, except `DEFAULT_PYTHON_VERSION`. Pins of one tool in several files SHALL share one group of every update type.

#### Scenario: The managers are read against the tracked files
- **WHEN** a test applies the file patterns and the match strings of the configuration to the tracked files
- **THEN** each pinned file matches its manager, and the custom managers find exactly the expected pins
- **AND** the coupled groups `uv`, `node`, `python runtime`, `ruff`, `actionlint`, `openspec`, `dcgm-exporter` and `devtools` set no update type
- **AND** the group `devtools` holds the devtools image of both Dockerfiles

#### Scenario: A uv or Node update changes no runtime code
- **WHEN** Renovate opens a pull request in the group `uv` or `node`
- **THEN** its diff holds no file under `src/devops_cli/`, and no `Fail-to-Pass Check` runs on it

### Requirement: Renovate titles fit the semantic title check
The preset SHALL write each title as `chore(deps): update <dependency> to <version>`, name an action without the word `action`, name a devcontainer feature by the last part of its reference, and add no `[SECURITY]` suffix, so that each summary has at most 60 characters.

#### Scenario: A title is built for each pinned dependency
- **WHEN** a test builds the summary of an update for each dependency that the repository pins, and for each group
- **THEN** no summary has more than 60 characters

### Requirement: Renovate pins no digest of a version input of an action
The shared preset `github>dan-petty/infra//renovate/base` SHALL pin the digests of github-actions and dockerfile dependencies, but not of a `uses-with` dependency of github-actions, such as the `version` input of setup-uv, because that input names a release tag and has no place for a digest.

#### Scenario: The digest pin rules are applied to each dependency type
- **WHEN** Renovate opens a pull request in devops-cli that moves the `version` input of setup-uv
- **THEN** the diff writes the new release tag to the input with no digest
- **AND** each `uses:` line and each `FROM` line that the diff changes names a digest

### Requirement: A security fix branch holds one update of each dependency
The shared preset `github>dan-petty/infra//renovate/base` SHALL set `vulnerabilityAlerts.separateMajorMinor` to false, so that the branch of a security fix holds only the newest fixed release of its dependency and never a minor and a major update of it together.

#### Scenario: The security settings are read
- **WHEN** an advisory names a fixed release in the current major and one in a newer major of a dependency that devops-cli pins, and the next run of CronJob `renovate` ends
- **THEN** one Renovate pull request of a security fix moves the dependency, and it moves it to the newest fixed release

### Requirement: A chart update has the prefix of a release
The repository configuration SHALL give each update of the `helm` datasource the prefix `fix(deps):`, because the update changes the chart that `deploy-stack` and Argo CD install: `deploy-stack` reads the version from the Application of the chart (#6060). Each coupled group that holds a chart SHALL set the same prefix.

#### Scenario: A chart update
- **WHEN** Renovate opens a pull request that moves a chart, alone or in the group `dcgm-exporter`
- **THEN** its title has the prefix `fix(deps):`, and release-please adds a changelog line for it

### Requirement: A Renovate update of runtime code has the prefix of a release
The repository configuration SHALL give each update that changes a file under `src/devops_cli/` the prefix `fix(deps):`, because the `Semantic PR title` check refuses a hidden type for runtime code and release-please must release the change. A group takes the prefix of its first update, so each group that holds such a file, and lock file maintenance, SHALL set the same prefix for each of their updates.

#### Scenario: An update of a pin under src
- **WHEN** Renovate opens a pull request that changes a file under `src/devops_cli/`, alone, in the group `python runtime`, `bandit` or `tools`, or as lock file maintenance
- **THEN** its title has the prefix `fix(deps):`, the `Semantic PR title` check passes with no manual retitle, and release-please adds a changelog line for it
- **AND** no update changes the runner tools table `RUNNER_TOOLS`, because it holds no version
