---
status: accepted
date: 2026-11-22
decision-makers: [owner]
issue: 6782
amends: ["0026"]
body-hash: "88b143cce2c28919d1584870da5453721720d2d37ec38645832bd5c13ef72cc1"
---

# The onboard command owns the repository settings

## Context and Problem Statement

[ADR 0026](0026-github-settings-are-opentofu-code-the-owner-applies.md) puts the settings of each repository in OpenTofu code that the owner applies (decisions 1, 4 and 7). Its root stacks, its GitHub module and its `tofu-state` namespace do not exist yet. The provider also cannot hold the `code_quality` rule of the `main` ruleset (`integrations/terraform-provider-github#3664` is open). No code applies a repository setting today: `devops roadmap onboard` creates only the missing labels. On 2026-11-22 the owner accepted the design of #6773 and its decisions D1 to D4.

## Decision Drivers

- A new repository gets each setting from one command run, and from no web UI step where GitHub has an API.
- Each setting has one copy and one owner.
- Only a person changes a repository setting (AGENTS.md).
- The decision works now, with no part of ADR 0026 as a prerequisite.
- No secret value goes into a repository, an output, a log or a plan.

## Considered Options

- **`devops repos onboard` applies one baseline from dan-petty/infra, and OpenTofu keeps the organization checks and the transfer check**: chosen.
- **OpenTofu holds the repository settings, as ADR 0026 decided**: rejected, because its stacks and state do not exist, and the provider cannot hold the `code_quality` rule of the ruleset.
- **The command and OpenTofu both hold the repository settings**: rejected, because two copies of one setting drift.
- **A repository secret for the release key of a private repository on the Free plan**: rejected, because each branch can read a repository secret.
- **A paid plan or public visibility for a private repository that needs releases**: deferred until the owner changes the plan or the visibility of that repository.
- **The person marks the template pull request ready and merges it**: rejected, because it adds a person step, and the required checks gate the merge in both cases.
- **The person adds the repository to `service.repos` and deploys by hand**: rejected, because it adds person steps that the command can do.

## Decision Outcome

Chosen option: "`devops repos onboard` applies one baseline from dan-petty/infra, and OpenTofu keeps the organization checks and the transfer check", because it works now, each setting has one copy, and a person still makes each change.

### 1. The command owns the repository settings (D1)

`devops repos onboard <owner>/<name>` applies the settings of a repository: the merge methods, the squash title and body, the security features, the environments, the variables and the rulesets. The values have one copy, the baseline in dan-petty/infra, at a release tag ([ADR 0032](0032-infrastructure-templates-live-in-four-homes.md)). A person runs the command with their own gh login.

- `--plan` sends GET requests only. `--dry-run` sends no request. `--confirm` writes.
- Each row reads the live value, compares it with the baseline and writes only a difference. On an onboarded repository, `--confirm` sends no write.
- `devops repos onboard --all --plan` is the drift check. It uses the same code path as the apply, and it exits 1 on a pending change.
- The command replaces `devops roadmap onboard` and takes over its rows.

### 2. OpenTofu keeps the organization checks and the transfer check

OpenTofu keeps the organization postconditions of ADR 0026 decision 5 and the transfer check of its decision 6. No OpenTofu resource writes a setting that the command owns.

### 3. A private repository on the Free plan gets no release flow (D2)

On the Free plan, GitHub gives environments only to public repositories, and the ruleset API answers 403 for a private repository. So such a repository gets no release-please workflow, no release key and no `release` environment. The command never stores a release key as a repository secret.

### 4. The command marks the template pull request ready and turns on auto-merge (D3)

The command opens the template pull request as a draft. After its checks pass, the command marks it ready and turns on auto-merge, with the login of the person who runs the command. The `main` ruleset requires only the checks that reported. So the person starts the merge with the command run, and no agent merges.

### 5. The command connects the Service (D4)

With `--confirm`, the command adds the repository to `service.repos` and runs `devops k8s push-secrets` and `devops k8s deploy-stack`. It does these steps only from a clean checkout of `origin/main` of devops-cli, so a deploy holds only merged code.

### 6. Amendments of ADR 0026

- **Decision 1.** The shared module and the root stacks hold no repository setting.
- **Decision 4.** The code manages only the organization baseline that a data source can read. The repository settings go to the command.
- **Decision 7.** The command manages the `main` ruleset of each repository, with the `code_quality` rule, and does not wait for the provider.
- **Alternatives.** ADR 0026 rejected a home-grown baseline, because it was a second copy of each setting. The baseline in infra is the only copy.

### Consequences

- Good, because a new public repository needs one command run and no web UI step, and the command can run now.
- Good, because each setting has one copy, and the drift check reads it with the code of the apply.
- Bad, because the project keeps its own apply code, which OpenTofu would give.
- Bad, because a private repository on the Free plan has no release flow.
- Bad, because the ruleset requires only the checks that reported on the template pull request, so a check that did not report then is not required.

### Confirmation

- The route-ownership test of #6773 lists each write route of the command. It fails when a route writes a setting of another owner: OpenTofu, the Service or the template.
- The nightly drift Job runs `devops repos onboard --all --plan`.
- On an onboarded repository, `devops repos onboard <owner>/<name> --confirm` sends no write and exits 0.

## More Information

- The design and the owner decisions: #6773, the comments of 2026-11-22.
- The records: [ADR 0026](0026-github-settings-are-opentofu-code-the-owner-applies.md) and [ADR 0032](0032-infrastructure-templates-live-in-four-homes.md).
- The GitHub pages: [repository rulesets](https://docs.github.com/en/rest/repos/rules#create-a-repository-ruleset), [environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments) and [Actions secrets](https://docs.github.com/en/rest/actions/secrets).
- The change: `openspec/changes/archive/2026-11-22-6782-adr-repository-settings/`.
