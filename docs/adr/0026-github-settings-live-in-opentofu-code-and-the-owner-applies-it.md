---
status: accepted
date: 2026-11-15
decision-makers: [owner]
issue: 5314
body-hash: "bc5f0c1fe948332759e810f04895c2d28ec1455fc7aca30a2939a7aca6111445"
---

# GitHub settings live in OpenTofu code, and the owner applies it

The plan of #5311 moves the repositories of `dan-petty` to the `retric-ai` owner. No record said where the settings of a repository or an organization live, who changes them, or how a person verifies a transfer. Three designs competed, and the owner chose the first (decisions 1, 4, 5 and 7 of #5311 on 2026-11-13).

## Context

- **Two owners, two provider blocks.** OpenTofu 1.13.9 with `integrations/github` 6.13.0 runs at exact pins that Renovate updates. Each provider block names one owner, so each owner needs a stack.
- **The state needs a home.** The Kubernetes backend holds it, as the rest of the stack does, in a new `tofu-state` namespace.
- **An agent plans and a person applies.** A new public App, `devops-settings-reader`, is owned by `retric-ai`, holds read permissions only and no webhook, and is installed on both accounts. Agents on a workstation and the drift job plan with it. Only the owner applies, because an apply changes accounts.
- **Some settings stay out of code.** Labels, secret values, webhooks, App registrations, packages, Projects and the organization security configuration stay out, because a secret value in the state is a leak, and the other objects need an owner's console.
- **The `main` ruleset of `devops-cli` stays unmanaged.** Upstream `integrations/terraform-provider-github#3664` is open, and an unmanaged ruleset is better than a wrong one.
- **A transfer is not a resource.** The provider has no transfer resource, and `gh` has no transfer verb (`cli/cli#5292`). The owner sends the API call, and an import-only plan proves that the two stacks hold the repository after the move.

## Decision

### 1. Two root stacks and one shared module

The settings live in `tf/github/dan-petty` and `tf/github/retric-ai`, one root stack for each owner. The shared module `tf/github/modules/repository` holds the repository settings. Import blocks with `for_each` stay in the code, so a plan rebuilds a lost state.

### 2. The Kubernetes backend holds the state

The state of both stacks lives in the Kubernetes backend, in the `tofu-state` namespace. No local state file and no state in git.

### 3. The reader App plans, and the owner applies

`devops-settings-reader` holds read permissions only and no webhook, and it is installed on both accounts. Agents plan with it. The owner applies each change to an account, because only a person changes repository settings (AGENTS.md, "Only a person").

### 4. The scope split holds

Code manages repository settings and the organization baseline that a data source can read. Labels, secret values, webhooks, App registrations, packages, Projects and the organization security configuration stay out of the state.

### 5. Postconditions assert, and checks only warn

A failed `check` block warns and the apply goes on. A `postcondition` fails the plan or the apply. The organization data source uses postconditions for 2FA, the default permission and member privileges, so `billing_email` never reaches the state, the plan or Loki. The owner changes those values in the UI.

### 6. A transfer is an owner call that an import-only plan verifies

The owner sends `devops gh api -X POST repos/{owner}/{repo}/transfer -f new_owner=retric-ai` in the move window, after the preflight reads. Then an import-only plan of the target stack shows the repository and its settings, and an import-only plan of the source stack shows none.

### 7. The `main` ruleset stays unmanaged until the provider fixes #3664

The ruleset of `devops-cli` stays in the GitHub UI. The record changes when the provider carries the ruleset without the upstream defect.

## Consequences

- An agent plans a settings change and a person applies it, so a wrong value reaches an account only through a person's apply.
- Two stacks repeat the provider version and the backend block. The shared module holds the settings, so the repetition is small.
- The state namespace is a new resource of the cluster, and its Secret is a cluster Secret of the process.
- The import-only plan is the check of a transfer, and it needs the reader App on both accounts.
- The ruleset of `devops-cli` is one setting that a person still changes by hand.

## Alternatives

- **safe-settings 3.0.0 as a policy App.** Rejected. Release 3.0.0 has no `repository.transferred` handler, it covers only the organization repositories, and it adds a service that the internet can reach with write access to each organization repository.
- **A thin audit CLI with a home-grown baseline.** Rejected. It does again what OpenTofu does, and it holds a second copy of each setting.
- **A transfer command in `devops-cli`.** Rejected for now. A runbook with preflight GETs and the owner call is enough while moves are rare. Build a command when moves become frequent.

## Status History

2026-11-15: Accepted by the owner, decisions 1, 4, 5 and 7 of #5311.
