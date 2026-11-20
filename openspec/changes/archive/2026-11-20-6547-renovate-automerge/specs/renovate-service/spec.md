## MODIFIED Requirements

### Requirement: A security fix of this repository merges itself after the required checks
The `vulnerabilityAlerts` object of `.github/renovate.json` SHALL set `automerge: true`, `automergeType: pr` and `platformAutomerge: true`, for each update type, so GitHub merges a security fix only after the required checks of the ruleset `main` pass. No other part of `.github/renovate.json` SHALL turn automerge on.

#### Scenario: The automerge scope
- **WHEN** Renovate opens a pull request for a security alert, and a person runs `uv run devops gh pr view <number>`
- **THEN** GitHub auto-merge is on for the security fix, and the security fix merges only after the required checks of the ruleset `main` pass

## ADDED Requirements

### Requirement: The shared preset merges minor, patch and digest updates after their checks
The shared preset `.github/renovate/base.json` SHALL set `automerge: true`, `automergeType: pr` and `platformAutomerge: false` for the update types `minor`, `patch` and `digest`, so Renovate merges such a pull request itself, on a later run, only when each check of the pull request passed. A major update, a pin and lock file maintenance SHALL wait for a person.

#### Scenario: The config validates
- **WHEN** a person runs `npx --yes --package renovate@44.239.2 renovate-config-validator --no-global .github/renovate/base.json .github/renovate.json`
- **THEN** the command exits 0

#### Scenario: A minor update with passing checks merges
- **WHEN** Renovate opens a pull request for a minor update in a repository that extends the preset, each check of the pull request passes, and the next run of CronJob `renovate` ends
- **THEN** the body of the pull request says that automerge is on, and Renovate has merged the pull request

#### Scenario: A failing check stops the merge
- **WHEN** a check of a Renovate pull request for a patch update fails, and the next run of CronJob `renovate` ends
- **THEN** the pull request is still open

#### Scenario: A major update waits for a person
- **WHEN** Renovate opens a pull request for a major update that is not a security fix
- **THEN** the body of the pull request says that automerge is off
