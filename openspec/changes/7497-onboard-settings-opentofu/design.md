# Design

## Context

`devops repos onboard` has 17 rows (`run.py:64-81`). Rows 1, 2, 3, 5 and 10 read the live settings, compare them with the rendered `github/repository.yaml` (`model.py:152-217`), and write each difference (`settings_rows.py:197-864`, `ruleset_merge.py`). CronJob `repos-drift` runs `--all --plan --only 0,...,11` each night (`k8s/devops/cronjob-repos-drift.yaml:85-91`). ADR 0041 gives these settings to OpenTofu. This design answers where the code lives, how each fact and each secret reaches it, who plans and applies, how the import changes nothing, what stays in the command, and the order of the work. The evidence comes from a scratch module and read-only plans of 2026-11-28 (OpenTofu v1.13.10, provider v6.13.0).

## Decisions

### D1. The roots, the module and the state

- **Module:** dan-petty/infra `tf/modules/github-repository` (dan-petty/infra#240). The public root calls it by a local path. The private root pins a release tag with `?ref=vX.Y.Z`, and Renovate updates the pin.
- **Public root:** dan-petty/infra `tf/github/dan-petty`, with the 9 public repositories of the account (dan-petty/infra#241). infra is public, and GitHub gives required reviewers to an environment of a public repository on each plan ("Deployments and environments": "If you are on a GitHub Free, GitHub Pro, or GitHub Team plan, required reviewers are only available for public repositories"). ADR 0032 section 8 kept the roots out of infra because they name private repositories. This root names none, so ADR 0041 amends that section.
- **Private root:** dan-petty/homelab `tf/github/dan-petty-private`, with homelab and the site repository (dan-petty/homelab#643). A public root would show their names in its code, its logs and its plan comments. The private-data guard of infra also refuses the real domain (`scripts/private-data-scan.sh`, rule `private-domain` from `PRIVATE_DOMAINS`), and the site repository has that name.
- **State:** the `kubernetes` backend of OpenTofu in namespace `tofu-state`, with `secret_suffix = "github-dan-petty"` and `"github-dan-petty-private"`. The backend keeps each state in Secret `tfstate-default-<suffix>` and locks with a Lease. The planned values of devops-cli are 7,844 bytes (2,130 gzip), so each state stays far below the 1 MiB limit of a Secret.
- **Pins:** `required_version` and the provider version are exact, and `.terraform.lock.hcl` is in git, as in `tf/examples/` of infra.

One root for each account and visibility gives one plan and one state for each, and keeps each private name in a private repository.

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
- The state then holds no secret value. RBAC of namespace `tofu-state` protects it: the ServiceAccount of the runner scale set of D7 writes it, and the drift identity of homelab#523 gets `get` and `list` only. State encryption is deferred: a passphrase is one more secret that the owner and the drift Job must hold, and it protects nothing that is secret.
- A check of the CI of each root (dan-petty/infra#241, dan-petty/homelab#359) keeps it so: `! git grep -nE 'resource "github_(actions_(environment_)?secret|actions_organization_secret|dependabot_secret|codespaces_secret|repository_webhook)"' -- tf/github`.

### D7. CI applies, and the owner approves each apply

The owner accepted this flow on 2026-11-28 ("proceed as recommended", after the merge of #7521): no person runs `tofu apply` in a terminal, CI applies, and the owner approves each apply with one click.

- **Where the jobs run.** A GitHub-hosted runner cannot reach the API server of the cluster, which holds the state. The S3 gateway of SeaweedFS is a ClusterIP Service behind `k8s/object-store/networkpolicy.yaml` of homelab, with no tunnel route. So the jobs run on a second runner scale set of actions-runner-controller, registered to dan-petty/infra (dan-petty/homelab#642), with ephemeral gVisor pods as `k8s/arc-runners/values.yaml` of homelab has. The scale set `runner-homelab` serves only homelab (`githubConfigUrl`), and a runner of a personal account serves one repository.
- **Kube credentials.** The pods run as one ServiceAccount with a projected token. A Role in `tofu-state` gives it `get`, `list`, `create`, `update` and `patch` on `secrets`, and `get`, `create`, `update` and `delete` on `leases`, and nothing else. Its NetworkPolicy admits the API server and public HTTPS only.
- **The risk of a self-hosted runner on a public repository.** GitHub says that "self-hosted runners should almost never be used for public repositories" ("Secure use reference"), because a fork pull request can run code on them. The owner sets the fork approval of infra to `all_external_contributors` (`PUT /repos/{owner}/{repo}/actions/permissions/fork-pr-contributor-approval`). A pod lives for one job, reaches only `tofu-state`, and holds no key that writes to GitHub outside the approved job. The import blocks rebuild a lost or changed state.
- **Pull request.** The job runs `tofu plan -refresh=false -lock=false`: the change of the pull request against the state, with no read of the live settings, so the merge settings show no false change (#3382). tfcmt v4.14.21 (MIT) posts it, the tool of #7503. The reader App gives the token for the read of a new import.
- **Push to `main`.** One job runs in environment `github-settings` of infra. Its required reviewer is the owner, and its branch policy is `main`. "A workflow job cannot access environment secrets until approval is granted by a reviewer" ("Secure use reference"). Only this environment holds the key of the writer App `devops-settings-writer`, which a person creates. After the approval, the job mints a token, runs `tofu plan` and `tofu apply` on both roots, and posts the result with tfcmt. One concurrency group runs one apply at a time. For the private root, the job checks out homelab, masks each private name with `::add-mask::`, and posts the plan only to homelab. A merge in homelab that changes that root starts the job with `workflow_dispatch`.
- **Agents.** An agent writes the pull request and reads the plan comment. It cannot apply: the key of the writer App is only in the approved job. Agents use the gh login of the owner, so #7534 makes `devops gh api` refuse an agent's review of a pending deployment (`POST repos/{owner}/{repo}/actions/runs/{run_id}/pending_deployments`), as it refuses the settings routes. `devops tf apply` still refuses an agent.
- **Who approves.** The owner, with one click on the pending deployment in the GitHub UI, after the plan comment of the pull request.
- **Drift.** #5328 stays in the cluster. It plans both roots with the token of `CONST_GITHUB_APP_DRIFT_TOKEN_PERMISSIONS` (#6888), because the reader App gets no merge settings (#3382). In infra, that token would need a key outside the approved environment.

### D8. What stays in `devops repos onboard`

Row numbers stay, so `--only` lists, scripts and documents keep their meaning. Rows 1, 2 and 5 go, and `--only` refuses their numbers with a message that names the root.

| Row | After the change |
| --- | --- |
| 0 Preflight | Stays. A missing repository fails with the step: add it to a root of OpenTofu, and the owner approves the apply. |
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

1. The owner accepts ADR 0041.
2. #7534: `devops gh api` refuses an agent's review of a pending deployment.
3. dan-petty/infra#240: the module, its `tofu test`, `tflint` and `trivy config`, and a release.
4. dan-petty/homelab#642: the runner scale set of infra and its access to `tofu-state`.
5. dan-petty/infra#241: the root with no entry, its checks and its workflow. The owner creates the writer App, environment `github-settings` with the owner as reviewer, the secrets and the fork approval.
6. dan-petty/infra#242: the probe dan-petty/dotfiles (public, no environment). The plan comment says `N to import, 0 to add, 0 to change, 0 to destroy`. The owner approves the apply, and then `tofu plan -detailed-exitcode` exits 0.
7. The owner runs the script of D5 for each repository whose `main` holds `code_quality` or `code_coverage`.
8. dan-petty/infra#243: the other public repositories, devops-cli last, each import proved as in step 6.
9. dan-petty/homelab#643: the private root, proved as in step 6.
10. devops-cli: the build pull request of this change (#7497). It goes after steps 6 to 9, so no setting is without a writer.
11. dan-petty/github-workflows#11: delete the settings file, the schema and the two questions, and release. Renovate brings the release, and `copier update` deletes `github/repository.yaml` in each consumer.
12. #5328: the drift job plans both roots.

### D10. Related items

- #7445 (which key differs) and #7305 (the client ID of the release App) end with the deleted rows: the plan names each attribute, and the root holds the client ID.
- #7309, #7310, #7406 and #7411 are faults of the template pull request (audit rank 16). This change does not touch them.
- #5325 returns to its stack form: the Pages site, `github-pages` and the collaborators of devops-cli go into the root, and dan-petty/infra#175 and #188 move there.
- #5329 (remove `devops gh branch-protection`) and #5311 (the plan of the settings as code) stay open.
- dan-petty/homelab#359 now checks only the private root, and dan-petty/homelab#360 (the root of retric-ai) follows the same split by visibility.

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
- **The owner applies from a terminal.** The owner chose one approval in the GitHub UI for each apply (D7).
- **The root in homelab with an environment gate.** homelab is private, and GitHub gives required reviewers to no private repository on the Free, Pro or Team plan.
- **An apply on merge with no approval.** The `main` rulesets of infra and homelab need 0 approvals (`required_approving_review_count: 0`), and agents merge with the gh login of the owner, so a merge is no person gate.
- **GitHub-hosted runners with the `kubernetes` backend.** They cannot reach the API server of the cluster.
- **An S3 backend on the SeaweedFS of the cluster, behind the tunnel.** The S3 gateway is internal (D7). A public route would put the object store, which holds other buckets, on the internet with key authentication only, because the S3 backend of OpenTofu sends no Cloudflare Access headers. A bucket outside the cluster (R2 or S3) with OpenTofu state encryption is deferred until the owner has one.
- **Runs with no state, from the import blocks only.** A resource that the configuration no longer lists is in no plan, and the server IDs of a new ruleset or policy must go back into `repositories.yaml`.
- **A plan with a refresh in the pull request job.** It needs a token that reads the merge settings (Contents write) outside the approved environment, or it shows them as `false -> true` (#3382).
- **The public root with the private repositories, their names masked.** The names stay in the code of a public repository, and the private-data guard of infra refuses the real domain (D1).
- **OpenTofu state encryption with `pbkdf2`.** D6: the state holds no secret value, and the passphrase is one more secret.
