# release-concurrency-and-renovate Specification

## Purpose
Isolate release workflow concurrency runs per branch reference, and configure automated Renovate dependency updates for Terraform, devcontainers, pre-commit, and GitHub Actions digest pins under taxonomy labels.

## Requirements

### Requirement: The release workflow isolates concurrency per branch
`.github/workflows/release.yml` SHALL configure its concurrency block with `group: release-${{ github.ref }}` and `cancel-in-progress: false`, so that release runs on separate branch references do not block or cancel one another.

#### Scenario: The release workflow manifest is read
- **WHEN** `.github/workflows/release.yml` is parsed as a workflow mapping
- **THEN** its `concurrency` property equals `{"group": "release-${{ github.ref }}", "cancel-in-progress": false}`

### Requirement: Renovate manages Terraform, devcontainers, pre-commit, and action digests under taxonomy labels
`.github/renovate.json` SHALL configure package rules for `terraform` (labeled `type/chore` and `scope/infra`), `devcontainer` (labeled `type/chore` and `scope/ci`), `pre-commit` (labeled `type/chore` and `scope/ci`), `github-actions` (with `pinDigests: true`), and SHALL disable `helm-values` and `helmv3`. It SHALL configure `rebaseWhen: "behind-base-branch"`.

#### Scenario: The Renovate configuration is read
- **WHEN** `.github/renovate.json` is parsed
- **THEN** it contains rules matching managers `terraform`, `devcontainer`, `pre-commit`, `github-actions`, and disabled `helm-values` and `helmv3`
- **AND** `rebaseWhen` is set to `"behind-base-branch"`

### Requirement: Renovate sets no minimum release age
`.github/renovate.json` SHALL hold no `minimumReleaseAge` and SHALL NOT extend `config:best-practices`, so that Renovate opens the pull request for a release with a security fix or a bug fix on the day it is published.

#### Scenario: The Renovate configuration is read
- **WHEN** a test reads `.github/renovate.json`
- **THEN** its text holds no `minimumReleaseAge`
- **AND** its `extends` list does not hold `config:best-practices`
