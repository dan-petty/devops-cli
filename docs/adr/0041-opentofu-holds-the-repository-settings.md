---
status: proposed
date: 2026-11-28
decision-makers: [owner]
issue: 7497
tracker: 5311
amends: ["0026", "0032"]
---

# OpenTofu holds the repository settings that the provider can hold

## Context and Problem Statement

[ADR 0035](0035-the-onboard-command-owns-the-repository-settings.md) gave the repository settings to `devops repos onboard`, because no OpenTofu stack existed and the provider cannot hold the `code_quality` rule (`integrations/terraform-provider-github#3664`). The command became its own desired-state engine, with 15 bug issues in 30 days (#7318, #7476, #7489). A read-only plan imports devops-cli with no change (#7497).

## Decision Drivers

- An open tool makes the plan, the diff, the apply and the drift check (AGENTS.md rule 3).
- Each setting has one copy and one writer.
- Only a person changes a repository setting (AGENTS.md), with one approval for each change.
- No secret value goes into a state, a plan or a log.

## Considered Options

- **OpenTofu with `integrations/github` holds each setting that the provider can hold, and onboard keeps the rest**: chosen.
- **`devops repos onboard` keeps its own settings engine**: rejected, because it cannot remove a required check (#7489).
- **The command and OpenTofu both hold one setting**: rejected, because two copies of one setting drift.
- **safe-settings 3.0.0 or repository-settings/app v5.0.16**: rejected, because each needs a hosted App with write access.
- **`Mastercard/restapi` 3.0.0 for the settings that `integrations/github` cannot hold**: deferred until a read-only import plan of those objects shows no change.
- **An apply by the owner from a terminal**: rejected, because the owner chose one approval in the GitHub UI.
- **An apply on merge with no approval**: rejected, because agents merge infra and homelab pull requests.
- **An approval gate in a private repository**: rejected, because GitHub gives required reviewers to no private repository on the Free, Pro or Team plan.
- **GitHub-hosted runners with a remote S3 state**: deferred until a bucket exists that they can reach.
- **Runs with no state, from the import blocks only**: rejected, because a removed resource is not in their plan.
- **Secret values of environments and webhooks in the state**: rejected, because provider 6.13.0 has no write-only argument (upstream #3202).
- **OpenTofu state encryption**: deferred until a resource of a root holds a secret value.
- **A repository secret for the release key of a private repository on the Free plan**: rejected, because each branch can read a repository secret.
- **A paid plan or public visibility for a private repository that needs releases**: deferred until the owner changes the plan or the visibility.
- **The person marks the template pull request ready and merges it**: rejected, because it adds a person step.
- **The person adds the repository to `service.repos` and deploys**: rejected, because the command does it.

## Decision Outcome

Chosen option: "OpenTofu with `integrations/github` holds each setting that the provider can hold, and onboard keeps the rest", because the provider plans, applies and finds drift with no project code.

### 1. The homes of the code and the state

This restores decision 1 of [ADR 0026](0026-github-settings-are-opentofu-code-the-owner-applies.md), and amends [ADR 0032](0032-infrastructure-templates-live-in-four-homes.md) section 8, because a public root names no private repository:

- dan-petty/infra holds the module `tf/modules/github-repository` and the root `tf/github/<owner>` of the public repositories.
- dan-petty/homelab holds the root `tf/github/<owner>-private` of the private repositories, with the module at an infra tag.
- `repositories.yaml` of a root holds the facts and the import IDs.
- Import blocks with `for_each` stay in the code, so a plan rebuilds a lost state.
- The Kubernetes backend holds the state in namespace `tofu-state`.

### 2. What OpenTofu holds

This restores decision 4 of ADR 0026. A root holds each repository, its vulnerability alerts, its workflow permissions, its `main` ruleset, and its environments with their branch policies and variables. Labels, secret values, webhooks, App registrations, packages, Projects and the organization security configuration stay out.

### 3. The `main` ruleset

This amends decision 7 of ADR 0026. A provider update drops each rule that the provider cannot hold (#3664), so `code_quality` and `code_coverage` go to a second ruleset, `quality`, which the owner keeps. GitHub applies the most restrictive rule of the rulesets of a branch.

### 4. What onboard keeps

`devops repos onboard` keeps the template pull request, the labels, the webhook, the release key, and the Service, cluster, RAG and OpenSpec rows. Each setting that provider 6.13.0 cannot hold keeps one API call that names its upstream item: private vulnerability reporting (#2399), immutable releases (#2746), code scanning default setup (#3315), the Code Quality setup (#2877), and the creation of ruleset `quality` (#3664).

### 5. CI applies, and the owner approves each apply

This amends decision 3 of ADR 0026:

- A pull request gets the plan of its change, `tofu plan -refresh=false`, as a tfcmt comment.
- A push to `main` of infra starts the apply job in environment `github-settings`. Its required reviewer is the owner, and only it holds the key of the writer App. The job applies both roots.
- The jobs run on a runner scale set of infra in the cluster, which can reach the state. Its ServiceAccount reaches only `tofu-state`, and a fork workflow needs the approval of the owner.
- `devops gh api` refuses an agent's review of a pending deployment, and `devops tf apply` refuses an agent.

### 6. Decisions of ADR 0035 that stay

A private repository on the Free plan gets no release flow and no repository secret for a release key. The command marks the template pull request ready with auto-merge, and connects the Service only from a clean `origin/main`.

### Consequences

- Good, because the owner sees each change in a plan before the approval, also a removal.
- Bad, because a public repository runs a self-hosted runner, which GitHub advises against.
- Bad, because five API calls stay until the provider holds their settings.

### Confirmation

- After the import, `tofu plan -detailed-exitcode` of each root exits 0.
- A push to `main` of infra waits for the approval of `github-settings`.
- A plan that removes a required check shows an update of `github_repository_ruleset`.
- The drift job of #5328 runs `tofu plan -detailed-exitcode` on each root.

## More Information

- The design and the evidence: `openspec/changes/7497-onboard-settings-opentofu/`.
- On acceptance, this record supersedes ADR 0035, and its pull request moves the citations of ADR 0035.
