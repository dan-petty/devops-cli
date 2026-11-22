## MODIFIED Requirements

### Requirement: The global config scopes Renovate to the App installation and onboards no repository yet
The global config SHALL set `platform: github`, `autodiscover: true`, `onboarding: false`, `requireConfig: required` and an `onboardingConfig` that extends `github>dan-petty/infra//renovate/base`. It SHALL hold no `token` and no `gitAuthor` in `config.json`, and SHALL name no Mend service.

#### Scenario: A repository with no config
- **WHEN** a Renovate run reaches a repository of the App installation that holds no Renovate config, and a person runs `kubectl -n devops logs <pod> -c renovate`
- **THEN** the log says that the run skips the repository, and the repository gets no onboarding pull request

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
