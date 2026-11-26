## MODIFIED Requirements

### Requirement: Renovate manages Terraform, devcontainers, pre-commit, and action digests under taxonomy labels
The shared preset `github>dan-petty/infra//renovate/base` SHALL label each update `type/chore` and `scope/deps`, add `scope/ci` to github-actions, pre-commit and devcontainer updates, add `scope/infra` to dockerfile, docker-compose, kubernetes, argocd, helm-values and terraform updates, pin the digests of github-actions and dockerfile, and turn the pre-commit manager on. Each label SHALL exist in `.github/labels.yml` or in the workflow labels.

#### Scenario: The Renovate configuration is read
- **WHEN** Renovate opens a pull request in devops-cli that updates an action, and a person runs `devops gh api repos/dan-petty/devops-cli/issues/<number> --jq '[.labels[].name]'`
- **THEN** the labels are `type/chore`, `scope/deps` and `scope/ci`
- **AND** each label is in `.github/labels.yml` or in the workflow labels of `src/devops_cli/roadmap/workflow_labels.py`

#### Scenario: An update of a chart
- **WHEN** Renovate opens a pull request in a repository of the preset that moves the chart of an Argo CD Application
- **THEN** the labels of the pull request are `type/chore`, `scope/deps` and `scope/infra`

### Requirement: Every pin of the repository has a Renovate manager
No rule SHALL turn off a manager. Each pinned file SHALL match a file pattern of its manager. Custom managers SHALL read the pins that no built-in manager reads: the Python minor. No custom manager SHALL write a tool version into a file under `src/`, except `DEFAULT_PYTHON_VERSION`. Pins of one tool in several files SHALL share one group of every update type.

#### Scenario: The managers are read against the tracked files
- **WHEN** a person reads the detected dependencies of the Dependency Dashboard of devops-cli
- **THEN** it lists each pinned file under its manager
- **AND** the coupled groups `uv`, `node`, `python runtime`, `ruff`, `actionlint`, `openspec` and `devtools` set no update type
- **AND** the group `devtools` holds the devtools image of both Dockerfiles

#### Scenario: A uv or Node update changes no runtime code
- **WHEN** Renovate opens a pull request in the group `uv` or `node`
- **THEN** its diff holds no file under `src/devops_cli/`, and no `Fail-to-Pass Check` runs on it

### Requirement: Release workflow requests owner review and Renovate avoids per-package automerge opt-outs
`.github/workflows/release.yml` SHALL include a `Request review on the release pull request` step in the `release-please` job using `steps.app.outputs.token` to request `dan-petty` on open release pull requests when the author is not `dan-petty` and `dan-petty` is not already requested. `.github/renovate.json` SHALL NOT override `automerge` to `false` on package rules, so approved updates merge automatically once checks pass.

#### Scenario: Release workflow and Renovate config pass validation
- **WHEN** a person or CI runs `uv run devops ci --check --only actionlint,zizmor` and `renovate-config-validator --strict --no-global .github/renovate.json`
- **THEN** both commands exit 0

## REMOVED Requirements

### Requirement: Renovate updates no environment path of the homelab repository
**Reason**: The environment files and the package rule that turned their updates off are deleted (#7290).
**Migration**: None.

### Requirement: A chart update has the prefix of a release
**Reason**: devops-cli pins no chart, and `.github/renovate.json` holds no `helm` rule (#7290).
**Migration**: None.
