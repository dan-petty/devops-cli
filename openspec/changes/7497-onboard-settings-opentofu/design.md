# Design

## Context

`devops repos onboard` has 17 rows (`run.py:64-81`). Rows 1, 2, 3, 5 and 10 read the live settings, compare them with the rendered `github/repository.yaml` (`model.py:152-217`), and write each difference (`settings_rows.py:197-864`, `ruleset_merge.py`). CronJob `repos-drift` runs `--all --plan --only 0,...,11` each night (`k8s/devops/cronjob-repos-drift.yaml:85-91`). ADR 0041 gives these settings to OpenTofu. This design answers where the code lives, how each fact and each secret reaches it, who plans and applies, how the import changes nothing, what stays in the command, and the order of the work. The evidence comes from a scratch module and read-only plans of 2026-11-28 (OpenTofu v1.13.10, provider v6.13.0).

## Decisions

### D1. The root, the module and the state

- **Module:** dan-petty/infra `tf/modules/github-repository`, at a release tag. ADR 0032 section 8 put the shared module in infra. A root pins it with `?ref=vX.Y.Z`, and Renovate updates the pin.
- **Root:** dan-petty/homelab `tf/github/dan-petty`, one root for each owner account. A provider block names one owner (ADR 0026, context), and the roots name private repositories (ADR 0032, section 8). homelab#360 adds `tf/github/retric-ai` later.
- **State:** the `kubernetes` backend of OpenTofu, namespace `tofu-state`, `secret_suffix = "github-dan-petty"`. The backend keeps the state in Secret `tfstate-default-github-dan-petty` and locks with a Lease. The planned values of devops-cli are 7,844 bytes (2,130 gzip), so 11 repositories stay far below the 1 MiB limit of a Secret.
- **Pins:** `required_version` and the provider version are exact, and `.terraform.lock.hcl` is in git, as in `tf/examples/` of infra.

One root for each account gives one plan, one state and one drift step for each account.

### D2. The facts of each repository

`tf/github/dan-petty/repositories.yaml` holds one entry for each repository. An entry holds only the values that differ from the module, and the IDs that an import needs. The root reads it with `yamldecode(file(...))` and calls the module with `for_each`.

```yaml
devops-cli:
  description: "..."
  has_projects: true
  has_discussions: true
  ruleset_id: 0            # the ID of the live ruleset main, for the import
  ruleset:
    include: ["refs/heads/main"]
    review_thread_resolution: true
    do_not_enforce_on_create: false
    code_scanning_alerts: errors_and_warnings
    code_scanning_security: medium_or_higher
    required_checks:
      - context: Static Analysis
      - context: Tests & Coverage
      - context: Semantic PR title
  release:
    policy_id: 0           # the ID of the branch policy main, for the import
```

- The variable `settings` of the module is an `object` with `optional()` defaults and `validation` blocks. These checks replace `templates/github-repository.schema.json`.
- The object conversion of OpenTofu drops an unknown key with no error (tested with YAML and with `terraform.tfvars`). So the root has an `output` with a `precondition` that fails the plan on a key that the module does not declare.
- The value of `RELEASE_APP_CLIENT_ID` is a root variable with one value for the account, because one release App serves each repository.
- The template keeps no copy. dan-petty/github-workflows deletes `templates/repository/github/repository.yaml.jinja`, `templates/github-repository.schema.json` and the questions `required_checks` and `code_coverage`, which only fed that file (`copier.yml:96-115`).

### D3. What the module declares

| Resource | Holds | Import ID |
| --- | --- | --- |
| `github_repository` | merge methods, squash title and body, auto-merge, update branch, delete branch, features, description, `security_and_analysis` (secret scanning and push protection) | `<repo>` |
| `github_repository_vulnerability_alerts` | the alerts (the attribute of `github_repository` is deprecated) | `<repo>` |
| `github_workflow_repository_permissions` | `read`, and no approval of a pull request | `<repo>` |
| `github_repository_ruleset` `main` | deletion, non fast-forward, pull request, required checks, code scanning | `<repo>:<id>` |
| `github_repository_environment` `release` | the branch policy setting | `<repo>:release` |
| `github_repository_environment_deployment_policy` | branch `main` | `<repo>:release:<id>` |
| `github_actions_environment_variable` | `RELEASE_APP_CLIENT_ID` | `<repo>:release:RELEASE_APP_CLIENT_ID` |

- `github_repository` has `lifecycle { prevent_destroy = true }`. It sets no `archive_on_destroy`, and it ignores changes of the deprecated `ignore_vulnerability_alerts_during_read`. An import leaves both null, and the first scratch plan showed both as a change.
- The module writes the required checks rule only when the list has a check, because the schema needs one `required_check` block at least (`tofu test` failed with `Insufficient required_check blocks`).
- A repository with `rulesets: false` gets no ruleset, and one with no `release` gets no environment, as ADR 0035 section 3 asks for a private repository on the Free plan.
- The environments that deployments make stay out (devops-cli has 14 of them, beside `release` and `github-pages`). `github-pages` and the Pages site go to the root with #5325.

### D4. The import changes nothing

- The root holds one `import` block with `for_each` for each resource of D3. The blocks stay in the code (ADR 0026, decision 1). An import block for a resource that the state holds does nothing, and after a state loss the plan imports again.
- The first entry of each live repository copies its live values. A change toward the baseline is a later pull request with its own plan.
- Evidence: the scratch root with the live values of devops-cli printed `Plan: 7 to import, 0 to add, 0 to change, 0 to destroy`. With one required check removed from the input, it printed an update of `github_repository_ruleset.main[0]` that removes that `required_check` (the case of #7489).
- `tofu test` with `mock_provider` passes on the module. On a root with import blocks, OpenTofu v1.13.10 crashed (exit 11). So the offline test runs on the module, and the root gets `tofu validate`, `tflint` and the plan of the owner.

### D5. The `main` ruleset and ruleset `quality`

- The live `main` ruleset of devops-cli holds `code_quality` and `code_coverage`. The provider read it with no change, but an update drops each rule that the provider does not model (#3664, issue text). So `main` must hold none of them before the first update.
- GitHub aggregates the rules of the rulesets of one branch, and the most restrictive version applies ("About rulesets"). A second ruleset `quality` holds `code_quality` and, where the live `main` has it, `code_coverage`.
- A one-time script of the owner creates `quality` in each repository from the live rules of `main`. Rulesets are routes that `devops gh api` refuses to an agent. After the script, the first apply that changes `main` drops the two rules from `main`.
- Row 10 of onboard creates `quality` with `code_quality` (severity `errors`) when a repository has none, and never writes it again. The owner changes a threshold in the GitHub UI until the provider holds the rules.

### D6. No secret value reaches OpenTofu

- Provider v6.13.0 has 0 write-only attributes and 0 ephemeral resources (`tofu providers schema -json`). `github_actions_environment_secret` keeps `value` or `value_encrypted` in the state, and `github_repository_webhook` keeps `configuration.secret`.
- So no root declares a secret resource or a webhook. The release key stays with row 6, which seals it and sends it through `gh` with the key from the keyring (`settings_rows.py:551-626`). The webhook stays with row 12 until #4417. This is decision 4 of ADR 0026.
- The state then holds no secret value. RBAC of namespace `tofu-state` protects it: the owner writes it, and the drift identity of homelab#523 gets `get` and `list` only. State encryption is deferred: a passphrase is one more secret that the owner and the drift Job must hold, and it protects nothing that is secret.
- A check of homelab CI keeps it so: `! git grep -nE 'resource "github_(actions_(environment_)?secret|actions_organization_secret|dependabot_secret|codespaces_secret|repository_webhook)"' -- tf/github`.

### D7. An agent plans, and the owner applies

- An agent changes `repositories.yaml` or the module in a pull request, and runs `devops tf plan <homelab>/tf/github/dan-petty -lock=false`. The guard of `tf-github-agent-guard` gives `tofu` a token of the read-only App `devops-settings-reader`. `devops tf apply` exits 1 for an agent at the default access `plan`.
- With that token, GitHub sends no merge settings, so the plan shows `false -> true` for them (upstream #3382). The agent reads the other lines. The plan of the owner and of the drift Job use a token that reads them.
- The owner approves a change by reading the plan and confirming `devops tf apply` in a person terminal with the owner's login. `tofu apply` asks for `yes`.
- An apply in CI does not fit. Agents merge every homelab pull request (homelab#538), so an apply on merge lets an agent change a setting, which AGENTS.md gives only to a person. GitHub gives required reviewers to no private repository on the Free, Pro or Team plan ("Deployments and environments"), so no environment gate can stop the job. A write key in CI is also a standing credential with Administration write on each repository.
- The drift Job of #5328 needs the permission set of `CONST_GITHUB_APP_DRIFT_TOKEN_PERMISSIONS` (#6888), not the reader App, or each night shows the merge settings as drift. It runs `tofu plan -detailed-exitcode -lock=false` only.

### D8. What stays in `devops repos onboard`

Row numbers stay, so `--only` lists, scripts and documents keep their meaning. Rows 1, 2 and 5 go, and `--only` refuses their numbers with a message that names the root.

| Row | After the change |
| --- | --- |
| 0 Preflight | Stays. A missing repository fails with the step: add it to `tf/github/<owner>`, and the owner applies. |
| 1 Create | Goes: `github_repository` creates the repository. |
| 2 Repository | Goes: `github_repository`. |
| 3 Security | Keeps private vulnerability reporting (#2399), immutable releases (#2746) and the default setup (pull request #3315). The alerts and the workflow permissions go. |
| 4 Code Quality | Stays (#2877). |
| 5 Environment | Goes: the environment resources. |
| 6 Release secret | Stays (D6). |
| 7 App check | Stays. |
| 8 Labels | Stays: the workflow labels of the package and `.github/labels.yml` (ADR 0026, decision 4). |
| 9 Template pull request | Stays, with no check names for row 10. |
| 10 Ruleset | Becomes "Quality ruleset" (D5). |
| 11 Ready | Stays. |
| 12 to 16 | Stay: webhook, Service, cluster, RAG, OpenSpec. |

Each row that stays compares its own value with the live value, with no shared diff. Each kept call has a code comment that names its upstream item, so a provider release that holds the setting shows which call to delete.

Deleted code, estimated from the function ranges at 70dc18c65:

| Part | Lines |
| --- | --- |
| `settings_rows.py`: rows 1, 2, 5, the provider part of row 3, the `main` part of row 10, their constants | about 520 |
| `ruleset_merge.py` | 255 |
| `model.py`: `differences`, `held_differences`, `_list_matches`, `change_lines` and 4 document constants | about 75 |
| `baseline.py`: `_checked_settings`, `read_repository_settings`, `SETTINGS_FILE`, `_SCHEMA_PATH` | about 45 |
| `routes.py`, `run.py`, `template_pr.py`: the routes, the order and the check names of the deleted rows | about 145 |
| Total | about 1,040 of 3,702; about 60 added |

### D9. Migration order

1. The owner accepts ADR 0041 (the merge of this pull request).
2. dan-petty/infra: the module, its `tofu test`, `tflint` and `trivy config`, and a release.
3. dan-petty/homelab: the CI check of homelab#359, extended with `tflint`, `trivy config` and the secret check of D6.
4. dan-petty/homelab: the root with one probe repository (dan-petty/dotfiles: public, no environment). An agent merges it.
5. The owner runs `tofu init`, then `tofu plan`, which must print `N to import, 0 to add, 0 to change, 0 to destroy`, then `tofu apply`. Then `tofu plan -detailed-exitcode` exits 0.
6. The owner runs the script of D5 for each repository whose `main` holds `code_quality` or `code_coverage`.
7. dan-petty/homelab: the other repositories, devops-cli last, each import proved as in step 5.
8. devops-cli: the build pull request of this change. It goes after step 7, so no setting is without a writer.
9. dan-petty/github-workflows: delete the settings file, the schema and the two questions, and release. The consumers take the release through Renovate, and `copier update` deletes `github/repository.yaml` in each repository.
10. #5328: the drift Workflow runs the plan of each root (D7).

### D10. Related items

- #7445 (which key differs) and #7305 (the client ID of the release App) end with the deleted rows: the plan names each attribute, and the root holds the client ID.
- #7309, #7310, #7406 and #7411 are faults of the template pull request (audit rank 16). This change does not touch them.
- #5325 returns to its stack form: the Pages site, `github-pages` and the collaborators of devops-cli go into the root, and dan-petty/infra#175 and #188 move there.
- #5329 (remove `devops gh branch-protection`) and #5311 (the plan of the settings as code) stay open.

## Rejected alternatives

- **One root for each repository.** It gives 11 backend blocks, 11 states and 11 plans for each drift run, and each root repeats the provider block. The state of 11 repositories fits in one Secret (D1: 7,844 bytes of planned values for devops-cli).
- **The root reads `github/repository.yaml` or `.copier-answers.yml` of each repository with `data "github_repository_file"`.** The plan of a homelab pull request then changes when another repository merges, and a new repository has no file before the first apply creates it. Required checks are a fact of the ruleset, which the root owns.
- **The REST bodies of the template as the input.** They are the REST bodies of the deleted engine, and their schema is 391 lines that the module types replace (`templates/github-repository.schema.json`).
- **`terraform.tfvars` in place of YAML.** It gives no stricter check: an unknown key passes in both forms on OpenTofu v1.13.10 (scratch test). The YAML file reads the same as the files of the template.
- **Labels in `github_issue_labels`.** The resource is authoritative and deletes each label that it does not list. Row 8 also creates the workflow labels of the package (`service_rows.py:132-148`, `WORKFLOW_LABELS`), and the Service and release-please write labels. ADR 0026 decision 4 keeps labels out.
- **`github_repository_webhook`.** Its secret goes into the state (D6), and #4417 removes the webhook of each repository.
- **One ruleset `main` with an API call that adds `code_quality` after each apply.** Two writers of one object: each apply drops the rule, and each run of the call adds it again (#3664).
- **`lifecycle { ignore_changes = all }` on `main`.** Upstream users of #3664 do this, but then the plan shows no change of `main`, also not the removal of a required check.
- **`Mastercard/restapi` 3.0.0 for the five calls.** It is maintained and Apache-2.0 (release of 2026-02-27). Four of the five endpoints are toggles with `PUT` and `DELETE` and no ID, or `PATCH` only, so each object needs method overrides. No read-only plan of these objects ran, so their drift behavior is not proved. Deferred, not refused.
- **The reader App for the drift Job.** It cannot read the merge settings (#3382, #6888), so each night would show drift.
- **An apply by CI with an App token, gated by an environment.** D7: agents merge homelab pull requests, and a private repository has no required reviewers on the Free, Pro or Team plan.
- **OpenTofu state encryption with `pbkdf2`.** D6: the state holds no secret value, and the passphrase is one more secret.
