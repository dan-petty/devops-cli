---
status: proposed
date: 2026-11-28
decision-makers: [owner]
issue: 7497
tracker: 5311
amends: ["0026"]
---

# OpenTofu holds the repository settings that the provider can hold

## Context and Problem Statement

[ADR 0035](0035-the-onboard-command-owns-the-repository-settings.md) gave the repository settings to `devops repos onboard`, because the OpenTofu stacks did not exist and the provider cannot hold the `code_quality` rule (`integrations/terraform-provider-github#3664`). The command became its own desired-state engine, with 15 bug issues in 30 days (#7318, #7476, #7489). The owner closed #7489, because an open tool does this work. Namespace `tofu-state` now exists. A read-only plan of provider 6.13.0 imports the settings of devops-cli with no change, and shows the removal of a required check (#7497).

## Decision Drivers

- An open tool makes the plan, the diff, the apply and the drift check (AGENTS.md rule 3).
- Each setting has one copy and one writer.
- Only a person changes a repository setting (AGENTS.md).
- No secret value goes into a state, a plan or a log.

## Considered Options

- **OpenTofu with `integrations/github` holds each setting that the provider can hold, and onboard keeps the rest**: chosen.
- **`devops repos onboard` keeps its own settings engine**: rejected, because it caused 15 bug issues in 30 days and cannot remove a required check (#7489).
- **The command and OpenTofu both hold one setting**: rejected, because two copies of one setting drift.
- **safe-settings 3.0.0 or repository-settings/app v5.0.16**: rejected, because each needs a hosted App with write access.
- **The REST provider `Mastercard/restapi` 3.0.0 for the settings that `integrations/github` cannot hold**: deferred until a read-only import plan of those objects shows no change.
- **An apply by CI with an App token**: rejected, because agents merge the homelab pull requests, and GitHub gives required reviewers to no private repository on the Free, Pro or Team plan.
- **Secret values of environments and webhooks in the state**: rejected, because provider 6.13.0 has no write-only argument (upstream #3202).
- **OpenTofu state encryption**: deferred until a resource of a root holds a secret value.
- **A repository secret for the release key of a private repository on the Free plan**: rejected, because each branch can read a repository secret.
- **A paid plan or public visibility for a private repository that needs releases**: deferred until the owner changes the plan or the visibility.
- **The person marks the template pull request ready and merges it**: rejected, because it adds a person step, and the required checks gate the merge in both cases.
- **The person adds the repository to `service.repos` and deploys**: rejected, because the command does it.

## Decision Outcome

Chosen option: "OpenTofu with `integrations/github` holds each setting that the provider can hold, and onboard keeps the rest", because the provider plans, applies and finds drift with no project code.

### 1. The homes of the code and the state

This restores decision 1 of [ADR 0026](0026-github-settings-are-opentofu-code-the-owner-applies.md) in the homes of [ADR 0032](0032-infrastructure-templates-live-in-four-homes.md), section 8:

- dan-petty/infra holds the module `tf/modules/github-repository`, at a release tag.
- dan-petty/homelab holds one root for each owner account, `tf/github/<owner>`.
- `repositories.yaml` of a root holds the facts of each repository that differ from the module, and the import IDs. The module types check them.
- Import blocks with `for_each` stay in the code, so a plan rebuilds a lost state.
- The Kubernetes backend holds the state in namespace `tofu-state`.

### 2. What OpenTofu holds

This restores decision 4 of ADR 0026. A root holds each repository, its vulnerability alerts, its workflow permissions, its `main` ruleset, and its environments with their branch policies and variables. Labels, secret values, webhooks, App registrations, packages, Projects and the organization security configuration stay out of the state.

### 3. The `main` ruleset

This amends decision 7 of ADR 0026. The provider holds the `main` ruleset. A provider update drops each rule that the provider cannot hold (#3664), so the `code_quality` and `code_coverage` rules go to a second ruleset, `quality`. GitHub applies the most restrictive rule of the rulesets of a branch. The owner keeps `quality` until the provider holds its rules.

### 4. What onboard keeps

`devops repos onboard` keeps the template pull request, the labels, the webhook, the release key, and the Service, cluster, RAG and OpenSpec rows. It keeps one API call for each setting that provider 6.13.0 cannot hold, and the code names the upstream item of each call:

- private vulnerability reporting (#2399);
- immutable releases (#2746);
- code scanning default setup (pull request #3315);
- the Code Quality setup (#2877);
- ruleset `quality`, which the command creates when it is missing (#3664).

### 5. An agent plans, and the owner applies

This keeps decision 3 of ADR 0026. An agent writes a root and runs `devops tf plan`, and `devops tf apply` refuses an agent. The owner reads the plan and applies it with the owner's login. No workflow or Job applies a root.

### 6. Decisions of ADR 0035 that stay

- A private repository on the Free plan gets no release flow and no repository secret for a release key (section 3).
- The command marks the template pull request ready and turns on auto-merge (section 4).
- The command connects the Service only from a clean `origin/main` (section 5).

### Consequences

- Good, because a plan shows each change, also the removal of a required check.
- Good, because about 1,000 lines of engine code go.
- Bad, because a new repository needs a homelab pull request and an apply by the owner.
- Bad, because the read-only reader App gets no merge settings, so its plan shows them as changes (upstream #3382).
- Bad, because five API calls stay until the provider holds their settings.

### Confirmation

- After the import, `tofu plan -detailed-exitcode` of each root exits 0.
- A plan that removes a required check from `repositories.yaml` shows an update of `github_repository_ruleset`.
- The route-ownership test of `devops repos onboard` fails on a route of a setting that OpenTofu holds.
- The drift job of #5328 runs `tofu plan -detailed-exitcode` on each root.

## More Information

- The design and the evidence: `openspec/changes/7497-onboard-settings-opentofu/`.
- On acceptance, this record supersedes ADR 0035, and its pull request moves the citations of ADR 0035.
- The provider: [integrations/terraform-provider-github](https://github.com/integrations/terraform-provider-github) v6.13.0, MIT.
- The GitHub pages: [about rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets) and [deployments and environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments).
