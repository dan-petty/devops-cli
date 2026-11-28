## Purpose

The contract of the OpenTofu code that holds the repository settings of each owner account (ADR 0041): the public root `tf/github/<owner>` and the module `tf/modules/github-repository` of dan-petty/infra, the private root `tf/github/<owner>-private` of dan-petty/homelab, their validators, the workflow that applies them after the approval of the owner, and the live checks that prove an import. `devops repos onboard` relies on this contract for each setting that it no longer writes.

## ADDED Requirements

### Requirement: OpenTofu holds the provider settings of each repository
The root `tf/github/<owner>` of dan-petty/infra SHALL declare each public repository of the account, and `tf/github/<owner>-private` of dan-petty/homelab each private one, through the module `tf/modules/github-repository`. The module SHALL declare the repository, its vulnerability alerts, its workflow permissions, its `main` ruleset and its environment `release`, and SHALL keep the repository with `prevent_destroy`.

#### Scenario: The roots validate
- **WHEN** the operator runs `tofu fmt -check -recursive`, `tofu init -backend=false`, `tofu validate` and `tflint` in each root
- **THEN** each command exits 0

#### Scenario: The module tests pass offline
- **WHEN** the operator runs `tofu test` in `tf/modules/github-repository` of dan-petty/infra, with `mock_provider "github"`
- **THEN** it passes, and a run with the visibility `internal` fails on the validation of `var.settings`

#### Scenario: Trivy finds no misconfiguration without a judgment
- **WHEN** the operator runs `trivy config` on the module and on each root
- **THEN** each finding has a judgment in `.trivyignore.yaml`, and GIT-0001 of a public repository has the judgment of the owner

### Requirement: A public root names no private repository
The root in dan-petty/infra SHALL name no private repository, and its logs and plan comments SHALL show no private repository name.

#### Scenario: The private-data guard of infra
- **WHEN** the CI of dan-petty/infra runs `scripts/private-data-scan.sh dir .` with `PRIVATE_DOMAINS`
- **THEN** it exits 0

#### Scenario: The log of an apply of the private root
- **WHEN** the owner reads the log of the job that applied `tf/github/<owner>-private`
- **THEN** each private repository name shows as `***`

### Requirement: The root pins its versions and keeps its state in tofu-state
Each root SHALL pin exact versions of OpenTofu and `integrations/github`, SHALL keep `.terraform.lock.hcl` in git, and SHALL keep its state in the `kubernetes` backend in namespace `tofu-state`, with one `secret_suffix` for each root.

#### Scenario: The state Secrets
- **WHEN** the operator runs `kubectl get secret -n tofu-state tfstate-default-github-dan-petty tfstate-default-github-dan-petty-private` after the first apply of each root
- **THEN** both Secrets exist, and `git ls-files tf/github` of each repository lists no state file

### Requirement: A pull request gets the plan of its change
A pull request that changes a root SHALL get `tofu plan -refresh=false -lock=false` of that root as a tfcmt comment, in the repository of the root.

#### Scenario: A change of one entry
- **WHEN** a pull request of dan-petty/infra changes one value of an entry of `repositories.yaml`
- **THEN** the pull request gets a comment that shows the update of that one attribute, and no change of the merge settings of another repository

### Requirement: CI applies after the owner approves
A push to `main` of dan-petty/infra, and a `workflow_dispatch` from dan-petty/homelab, SHALL start one job in environment `github-settings` of infra, whose required reviewer is the owner and whose branch policy is `main`. Only that environment SHALL hold the key of the writer App. No other job SHALL run `tofu apply`. `devops gh api` SHALL refuse an agent's review of a pending deployment (#7534), and `devops tf apply` SHALL refuse an agent.

#### Scenario: The apply waits for the owner
- **WHEN** a pull request that changes `repositories.yaml` merges into `main` of infra
- **THEN** the run shows the job as waiting for review in `github-settings`, and the job starts only after the owner approves it

#### Scenario: No other job applies
- **WHEN** the operator runs `! git grep -n -E "(tofu|devops tf) apply" -- .github k8s` in dan-petty/homelab and in devops-cli
- **THEN** each command exits 0

### Requirement: The jobs run where the state is
The jobs of the roots SHALL run on the runner scale set of dan-petty/infra in the cluster. Its ServiceAccount SHALL reach only the Secrets and the Leases of namespace `tofu-state`, and the fork approval of infra SHALL be `all_external_contributors`.

#### Scenario: The access of the runner
- **WHEN** a job on the runner label runs `kubectl auth can-i create leases -n tofu-state` and `kubectl auth can-i get secrets -n devops`
- **THEN** the first prints `yes` and the second prints `no`

### Requirement: The import changes nothing
Each root SHALL hold one `import` block with `for_each` for each resource of the module, and the blocks SHALL stay in the code. The first entry of a live repository in `repositories.yaml` SHALL copy its live values, so the first apply changes no setting on GitHub.

#### Scenario: The first plan
- **WHEN** the apply job of an import shows its plan, before the owner approves the apply
- **THEN** the summary is `<n> to import, 0 to add, 0 to change, 0 to destroy`

#### Scenario: After the import
- **WHEN** the drift job runs `tofu plan -detailed-exitcode` after the import apply
- **THEN** the command exits 0

#### Scenario: A lost state
- **WHEN** the state Secret of a root is gone, and the job runs `tofu plan`
- **THEN** the plan imports each resource, and adds, changes and destroys none

### Requirement: A plan shows the removal of a required check
A change of the required checks of a repository in `repositories.yaml` SHALL show in the plan as an update of its `github_repository_ruleset`, also when the change removes a check.

#### Scenario: One required check less
- **WHEN** one entry of `required_checks` of a repository is removed from `repositories.yaml`, and the pull request gets its plan
- **THEN** the plan updates `github_repository_ruleset.main` of that repository in place, and the change removes the `required_check` of that name

### Requirement: An unknown key of the facts fails the plan
Each root SHALL fail the plan when an entry of `repositories.yaml` holds a key that the module does not declare, because the object conversion of OpenTofu drops an unknown key with no error.

#### Scenario: A misspelled key
- **WHEN** an entry of `repositories.yaml` holds `vissibility`, and the pull request gets its plan
- **THEN** the plan fails with an error that names the repository and the key

### Requirement: The state holds no secret value
No root and no module SHALL declare a resource that keeps a secret value in the state: an Actions, Dependabot or Codespaces secret, or a webhook. `devops repos onboard` keeps the release key and the webhook.

#### Scenario: No secret resource
- **WHEN** the operator runs `! git grep -nE 'resource "github_(actions_(environment_)?secret|actions_organization_secret|dependabot_secret|codespaces_secret|repository_webhook)"' -- tf/` in dan-petty/infra and in dan-petty/homelab
- **THEN** each command exits 0

### Requirement: The main ruleset holds only rules of the provider
The `main` ruleset of each repository SHALL hold no rule that `integrations/terraform-provider-github` cannot hold. The rules `code_quality` and `code_coverage` SHALL live in the ruleset `quality` of the repository until the provider holds them (`integrations/terraform-provider-github#3664`).

#### Scenario: The rules of the two rulesets
- **WHEN** the operator runs `devops gh api repos/<owner>/<repo>/rulesets/<id> --jq '[.rules[].type]'` for the rulesets `main` and `quality` after the first apply that changes `main`
- **THEN** the types of `main` hold neither `code_quality` nor `code_coverage`, and the types of `quality` hold `code_quality`
