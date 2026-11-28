## Purpose

The contract of the OpenTofu code that holds the repository settings of each owner account (ADR 0041): the root `tf/github/<owner>` of dan-petty/homelab, the module `tf/modules/github-repository` of dan-petty/infra, their validators, and the live checks that prove an import, a plan and the person apply. `devops repos onboard` relies on this contract for each setting that it no longer writes.

## ADDED Requirements

### Requirement: OpenTofu holds the provider settings of each repository
The root `tf/github/<owner>` of dan-petty/homelab SHALL declare each repository of the owner account through the module `tf/modules/github-repository` of dan-petty/infra at a release tag. The module SHALL declare the repository with its merge settings, features and `security_and_analysis`, its vulnerability alerts, its workflow permissions, its `main` ruleset, and its environment `release` with its branch policy and `RELEASE_APP_CLIENT_ID`. The repository resource SHALL have `prevent_destroy`.

#### Scenario: The root validates
- **WHEN** the operator runs `tofu fmt -check -recursive`, `tofu init -backend=false`, `tofu validate` and `tflint` in `tf/github/dan-petty` of dan-petty/homelab
- **THEN** each command exits 0

#### Scenario: The module tests pass offline
- **WHEN** the operator runs `tofu test` in `tf/modules/github-repository` of dan-petty/infra, with `mock_provider "github"`
- **THEN** it passes, and a run with the visibility `internal` fails on the validation of `var.settings`

#### Scenario: Trivy finds no misconfiguration without a judgment
- **WHEN** the operator runs `trivy config` on the module and on the root
- **THEN** each finding has a judgment in `.trivyignore.yaml`, and GIT-0001 of a public repository has the judgment of the owner

### Requirement: The root pins its versions and keeps its state in tofu-state
The root SHALL pin exact versions of OpenTofu and `integrations/github`, SHALL keep `.terraform.lock.hcl` in git, and SHALL keep its state in the `kubernetes` backend in namespace `tofu-state` with one `secret_suffix` for each owner account.

#### Scenario: The state Secret
- **WHEN** the owner runs `kubectl get secret -n tofu-state tfstate-default-github-dan-petty` after the first apply
- **THEN** the Secret exists, and `git ls-files tf/github` of dan-petty/homelab lists no state file

### Requirement: The import changes nothing
The root SHALL hold one `import` block with `for_each` for each resource of the module, and the blocks SHALL stay in the code. The first entry of a live repository in `repositories.yaml` SHALL copy its live values, so the first apply changes no setting on GitHub.

#### Scenario: The first plan
- **WHEN** the owner runs `tofu plan` on the root before the first apply
- **THEN** the summary is `<n> to import, 0 to add, 0 to change, 0 to destroy`

#### Scenario: After the import
- **WHEN** the owner runs `tofu plan -detailed-exitcode` after the import apply
- **THEN** the command exits 0

#### Scenario: A lost state
- **WHEN** the state Secret of the root is gone, and the owner runs `tofu plan`
- **THEN** the plan imports each resource, and adds, changes and destroys none

### Requirement: A plan shows the removal of a required check
A change of the required checks of a repository in `repositories.yaml` SHALL show in the plan as an update of its `github_repository_ruleset`, also when the change removes a check.

#### Scenario: One required check less
- **WHEN** one entry of `required_checks` of a repository is removed from `repositories.yaml`, and `tofu plan` runs
- **THEN** the plan updates `github_repository_ruleset.main` of that repository in place, and the change removes the `required_check` of that name

### Requirement: An unknown key of the facts fails the plan
The root SHALL fail the plan when an entry of `repositories.yaml` holds a key that the module does not declare, because the object conversion of OpenTofu drops an unknown key with no error.

#### Scenario: A misspelled key
- **WHEN** an entry of `repositories.yaml` holds `vissibility`, and `tofu plan` runs
- **THEN** the plan fails with an error that names the repository and the key, and sends no write

### Requirement: The state holds no secret value
No root and no module SHALL declare a resource that keeps a secret value in the state: an Actions, Dependabot or Codespaces secret, or a webhook. `devops repos onboard` keeps the release key and the webhook.

#### Scenario: No secret resource
- **WHEN** the operator runs `! git grep -nE 'resource "github_(actions_(environment_)?secret|actions_organization_secret|dependabot_secret|codespaces_secret|repository_webhook)"' -- tf/` in dan-petty/homelab and in dan-petty/infra
- **THEN** each command exits 0

### Requirement: The main ruleset holds only rules of the provider
The `main` ruleset of each repository SHALL hold no rule that `integrations/terraform-provider-github` cannot hold. The rules `code_quality` and `code_coverage` SHALL live in the ruleset `quality` of the repository until the provider holds them (`integrations/terraform-provider-github#3664`).

#### Scenario: The rules of the two rulesets
- **WHEN** the operator runs `devops gh api repos/<owner>/<repo>/rulesets/<id> --jq '[.rules[].type]'` for the rulesets `main` and `quality` after the first apply that changes `main`
- **THEN** the types of `main` hold neither `code_quality` nor `code_coverage`, and the types of `quality` hold `code_quality`

### Requirement: The owner applies, and an agent plans
Only a person SHALL apply a root. No workflow, CronJob or Workflow SHALL run `tofu apply`. An agent SHALL plan through `devops tf plan`, which `tf-github-agent-guard` gives a read-only token, and `devops tf apply` SHALL refuse an agent. A plan that must show no merge-settings change SHALL use a token with Contents write and Administration write that sends GET requests only, because GitHub gives the merge settings only to such a token (upstream #3382, #6888).

#### Scenario: No job applies
- **WHEN** the operator runs `! git grep -n -E "(tofu|devops tf) apply" -- .github k8s` in dan-petty/homelab and in devops-cli
- **THEN** each command exits 0

#### Scenario: The plan of the owner
- **WHEN** the owner runs `devops tf plan` on the root with the owner's login, after an apply
- **THEN** the plan shows no change of the merge settings
