# renovate-service Specification

## Purpose
How self-hosted Renovate runs in namespace `devops`: the CronJob and its pinned image, the token init container that alone reads the App key, the pod controls under a read-only root, the global config, the cache claim, the network perimeter, the Secret row and the records of its license exception. Renovate runs commands that a repository names, so its pod holds no key of the Service and reaches no internal service.

## Requirements

### Requirement: The Secret row holds the two IDs and the key under their variables
The cluster secret table SHALL hold `devops/renovate`, an optional-feature Secret in stack `devops` with no restart, and three optional keys: the variables of `renovate.github_app_id` and `renovate.github_app_installation_id` from their settings, and of `renovate.github_app_private_key` from its keyring entry. The token container SHALL take it as optional.

#### Scenario: The push
- **WHEN** a person runs `uv run devops k8s push-secrets --stack devops --dry-run`
- **THEN** the dry run writes Secret `devops/renovate` with the keys `DEVOPS_CLI_RENOVATE_GITHUB_APP_ID`, `DEVOPS_CLI_RENOVATE_GITHUB_APP_INSTALLATION_ID` and `DEVOPS_CLI_RENOVATE_GITHUB_APP_PRIVATE_KEY` and no restart, with no value in the output

#### Scenario: A workstation with no Renovate settings
- **WHEN** `devops k8s push-secrets --stack devops` runs with no Renovate setting and no keyring entry
- **THEN** the push skips the three keys with a warning, writes no Secret `renovate`, and exits 0

### Requirement: A security fix of this repository merges itself after the required checks
The `vulnerabilityAlerts` object of `.github/renovate.json` SHALL set `automerge: true`, `automergeType: pr` and `platformAutomerge: true`, for each update type, so GitHub merges a security fix only after the required checks of the ruleset `main` pass. No other part of `.github/renovate.json` SHALL turn automerge on.

#### Scenario: The automerge scope
- **WHEN** Renovate opens a pull request for a security alert, and a person runs `uv run devops gh pr view <number>`
- **THEN** GitHub auto-merge is on for the security fix, and the security fix merges only after the required checks of the ruleset `main` pass

### Requirement: The shared preset merges minor, patch and digest updates after their checks
The shared preset `github>dan-petty/infra//renovate/base` SHALL set `automerge: true`, `automergeType: pr` and `platformAutomerge: false` for the update types `minor`, `patch` and `digest`, so Renovate merges such a pull request itself, on a later run, only when each check of the pull request passed. A major update, a pin and lock file maintenance SHALL wait for a person.

#### Scenario: The config validates
- **WHEN** a person runs `npx --yes --package renovate@44.239.2 -- renovate-config-validator --strict --no-global .github/renovate.json`
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
