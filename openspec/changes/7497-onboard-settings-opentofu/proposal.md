# Proposal: #7497

## Why

`devops repos onboard` holds its own desired-state engine for the repository settings (#7497). It reads each live setting, compares it with `github/repository.yaml`, and writes each difference through REST. In 30 days the engine caused 15 bug issues and 5 fix pull requests. Three ruleset bugs came on 2026-11-27: #7318, #7476 and #7489. The owner closed #7489 as not planned, because an open tool does this work: the OpenTofu provider `integrations/github`. ADR 0035 chose the engine only because the OpenTofu stacks did not exist and the provider cannot hold the `code_quality` rule. The namespace of the state now exists, and the provider imports the settings of devops-cli with no change (see Feasibility).

## What Changes

- A new decision record, ADR 0041, replaces ADR 0035 and amends decisions 1, 4 and 7 of ADR 0026. OpenTofu holds each repository setting that provider 6.13.0 can hold. One root for each owner account in dan-petty/homelab (`tf/github/<owner>`) calls the module `tf/modules/github-repository` of dan-petty/infra. The owner applies.
- ADR 0026 gets the new amendment. This pull request holds the plan and the proposed record only, with no code. When the owner accepts the decision, the same pull request makes ADR 0041 supersede ADR 0035, moves the five citations of ADR 0035 in `src/` and `tests/` (which `tests/invariants/test_adr_superseded_citations.py` requires), and changes row ACC-3 of `docs/guidelines/production-readiness.md` with its entry in `READINESS_ROWS` (task 1.3).
- The build pull request of this change deletes these parts of `devops repos onboard`, because a root holds their settings:
  - row 1 (create), row 2 (repository) and row 5 (environment);
  - the vulnerability alerts and the workflow permissions of row 3;
  - the `main` ruleset of row 10, with `ruleset_merge.py` and the check names that row 9 records for row 10;
  - the diff of `model.py` and the schema check of `github/repository.yaml` in `baseline.py`;
  - the options `--create` and `--visibility`, and the routes and the tests of these rows.
- Row 3 keeps the API calls of private vulnerability reporting, immutable releases and the code scanning default setup. Row 4 keeps the Code Quality setup. Row 10 creates a ruleset `quality` with the `code_quality` rule when the repository has none. The code names the upstream item of each call.
- CronJob `repos-drift` runs only the rows that stay.
- The change alters what `devops repos onboard` prints and writes, so it carries spec deltas: `repos-onboard`, `repos-drift-alerts` and the new capability `github-settings-opentofu`.
- The change does not fit one pull request. It needs work in four repositories, in the order of the design. This pull request holds the plan and the decision record. The devops-cli build is one more pull request. The module, the root and the template each need a pull request in their own repository.

## Capabilities

### New Capabilities

- `github-settings-opentofu`: the contract of the OpenTofu roots that hold the repository settings, with its validators and live checks.

### Modified Capabilities

- `repos-onboard`: the rows that a root holds go, row 10 creates ruleset `quality` only, and the baseline has no `github/repository.yaml`.
- `repos-drift-alerts`: the Job runs only the rows that stay.

## Impact

- This pull request: `docs/adr/0041-opentofu-holds-the-repository-settings.md` (new), `docs/adr/0026-github-settings-are-opentofu-code-the-owner-applies.md`, `docs/adr/README.md` and this change folder. On acceptance (task 1.3): `docs/adr/0035-the-onboard-command-owns-the-repository-settings.md`, `docs/guidelines/production-readiness.md`, `src/devops_cli/roadmap/project_review/readiness.py` and the five files that cite ADR 0035.
- The build pull request: `src/devops_cli/github/onboard/`, `src/devops_cli/commands/repos.py`, `src/devops_cli/lang/en/help.py`, `tests/github/onboard/`, `tests/commands/test_repos_onboard.py`, `tests/support/github_repository.py`, `k8s/devops/cronjob-repos-drift.yaml`, `docs/repos/onboard.md`, `docs/CLUSTER.md`, `docs/commands/repos.md`, `docs/CLI_REFERENCE.md` and `k8s/README.md`.
- Other repositories: dan-petty/infra (the module), dan-petty/homelab (the root, its CI and the import), dan-petty/github-workflows (the template loses `github/repository.yaml.jinja`, `github-repository.schema.json` and the questions `required_checks` and `code_coverage`).
- Size: `src/devops_cli/github/onboard/` has 3,702 lines (`wc -l` at 70dc18c65). The build deletes about 1,040 of them and adds about 60 (an estimate from the function ranges; task 3.6 measures it). `tests/github/onboard/` has 84 tests; about 34 go (the 11 of `test_onboard_ruleset_merge.py` and about 23 of `test_onboard_rows.py`, by test name). The template change deletes 510 lines (119 of `repository.yaml.jinja`, 391 of the schema).

## Feasibility

- Provider: integrations/terraform-provider-github v6.13.0 of 2026-07-08 is the newest release on 2026-11-28 (`devops gh api repos/integrations/terraform-provider-github/releases/latest`), MIT. OpenTofu v1.13.10 is on PATH.
- A read-only plan with the person login of the devcontainer, a scratch module and import blocks with `for_each` for devops-cli printed `Plan: 7 to import, 0 to add, 0 to change, 0 to destroy`. Two corrections were necessary: the root must declare `description`, and the module must not set `archive_on_destroy` (an import leaves it null, so the plan showed a change). The deprecated `ignore_vulnerability_alerts_during_read` needs `ignore_changes`, for the same reason.
- The plan read the live `main` ruleset of devops-cli, which holds `code_quality` and `code_coverage`, and showed no change. Upstream #3664 says that a provider update drops these rules. So they move to their own ruleset.
- The same plan with one required check removed from the input printed `github_repository_ruleset.main[0] will be updated in-place` with `- required_check { - context = "Semantic PR title" }`. This is the case of #7489.
- The provider has no resource for private vulnerability reporting (upstream #2399), immutable releases (#2746), the code scanning default setup (pull request #3315, open since 2026-06-03) or the Code Quality setup (#2877). The schema of v6.13.0 has no `code_quality` or `code_coverage` rule (`tofu providers schema -json`), and 0 write-only attributes (upstream #3202 is open, pull request #3689 closed unmerged on 2026-11-25).
- With a token that has no Contents write, GitHub sends no merge settings, and the provider reads them as `false` (upstream #3382). The drift Job of onboard already asks for Contents write and Administration write for this reason (#6888, `CONST_GITHUB_APP_DRIFT_TOKEN_PERMISSIONS`).
- The 9 repositories of the onboard runs of 2026-11-26, dan-petty/github-workflows and dan-petty/acp each have one ruleset `main`: 11 of 11 (a read of `repos/dan-petty/<name>/rulesets` for each). Four of them have an environment `release`, and devops-cli also has `github-pages`. Two are private.
- `devops tf apply` already refuses an agent on a `tf/github` stack, and an agent plan already gets a read-only reader token (capability `tf-github-agent-guard`).
- The module scratch test: `tofu test` with `mock_provider "github"` passes offline, and a visibility of `internal` fails its run. `tofu validate` does not check the values of `repositories.yaml`. An unknown key passes the type conversion with no error (tested with YAML and with `terraform.tfvars`).
- `tflint` 0.66.0 passes on the module. `trivy config` reports GIT-0001 (CRITICAL, "Repository is public") for a public repository, which the owner must judge (SECURITY.md, "Judging a Trivy-config Alert").

## Existing Tool Considered

OpenTofu (MPL-2.0) with integrations/terraform-provider-github v6.13.0 (MIT) covers the repository, the security settings that it models, the vulnerability alerts, the workflow permissions, the `main` ruleset, the environments, their branch policies and their variables. `tofu plan` gives the diff and the drift check, and `tofu apply` the write. The change deletes the internal engine: the diff of `model.py` (`differences`, `held_differences`, `_list_matches`, `change_lines`), `ruleset_merge.py`, rows 1, 2 and 5, the provider part of row 3, the `main` part of row 10, the schema check of `baseline.py`, and their routes and tests. In dan-petty/github-workflows it deletes the REST bodies of `github/repository.yaml.jinja` and the hand-written schema. The five API calls that stay have no provider resource in v6.13.0. The generic REST provider `Mastercard/restapi` 3.0.0 (Apache-2.0) could hold them, but no read-only plan proves its drift behavior on these endpoints, so the design defers it.

## Dependencies

- The owner accepts ADR 0041: the merge of this pull request.
- The module in dan-petty/infra, the root `tf/github/dan-petty` in dan-petty/homelab, and the import of each repository by the owner, before the build pull request of devops-cli (design, "Migration order").
