---
status: accepted
date: 2026-11-21
decision-makers: [owner]
issue: 6674
amends: ["0026", "0027"]
body-hash: "552c4ed9e8a6a119ae8724c36dbc0ea07836d6fbb10bf1ff837247b83994a927"
---

# Infrastructure templates live in four homes

## Context and Problem Statement

No record says which repository holds an infrastructure template. With no rule, agents planned the rows of one site in this repository (#6642 to #6649). [ADR 0026](0026-github-settings-are-opentofu-code-the-owner-applies.md) puts a shared OpenTofu module and two root stacks that name private repositories here. [ADR 0027](0027-dependency-updates-come-from-self-hosted-renovate.md) puts the self-hosted Renovate in `k8s/devops`, but it serves every repository of the owner. The owner gave the end state on 2026-11-21. The public repository dan-petty/infra (MIT) is onboarded and holds no template yet.

## Decision Drivers

- Each repository holds only the files that it is responsible for.
- A shared template has one copy, and each consumer takes its changes at a release.
- A public repository holds no private data.
- A new service repository needs no code, row or constant in the platform.

## Considered Options

- **Four homes, release tags of infra, and one services entry for each service**: chosen.
- **Keep every template in devops-cli**: rejected, because the product then holds the stacks and the rows of other services.
- **Put the shared templates in dan-petty/homelab**: rejected, because homelab is private and holds the values of one environment.
- **Pin infra at `main`**: rejected, because a remote base at HEAD "can suddenly change meaning" (Argo CD best practices).
- **A tag for each component, an OCI artifact or a git submodule**: rejected, because one repository tag that Renovate updates is enough.
- **The root stacks of ADR 0026 in public infra**: rejected, because they name private repositories.

## Decision Outcome

Chosen option: "Four homes, release tags of infra, and one services entry for each service", because each file then has one home, and a consumer takes a shared change only at a tag.

### 1. The four homes

- **dan-petty/devops-cli** keeps only the templates of its own deployment: the Service, the roadmap jobs and their schedules (`k8s/devops`).
- **A service repository**, such as dan-petty/danielpetty.com, keeps the templates of its own stack.
- **dan-petty/infra** keeps the shared configuration templates and the general settings.
- **dan-petty/homelab** keeps each sensitive value and the configuration of the resources on the homelab nodes and cluster: the inventory, the hosts, the domain, the sizes, the overrides and the Secret sources.

### 2. The placement rule

A template that only one consumer uses lives with that consumer. A template that two or more consumers use, or a platform stack that any service can use, lives in infra. The README of each infra template names its consumers. The platform never holds a row, a constant, a namespace, an alert or a dashboard of one service.

### 3. Consumers pin infra at a release tag

infra releases one repository tag `vX.Y.Z`. A consumer pins the tag with a Kustomize `?ref=`, an Argo CD `ref` source, the Ansible collection from git, an OpenTofu `?ref=` or a reusable workflow `@vX.Y.Z`. Renovate updates each pin. The environment repository keeps `targetRevision: main` for its own sources. A consumer extends a Renovate preset of infra from its default branch (dan-petty/infra#6).

### 4. The release App tags infra

release-please makes the tags of infra (dan-petty/infra#5). The devops-cli release App opens its release pull request (owner decision of 2026-11-21), because a pull request that `GITHUB_TOKEN` opens starts no workflow. The credentials of the App are in an environment `release` of infra. Each GitHub App of the account is installed on every dan-petty repository, so infra needs an environment and no installation. This changes point 3 of [ADR 0011](0011-releases-come-from-trunk-towncrier-uv-and-semver-tags-instead-of-a-bespoke-cut.md), which gave the App to this repository only.

### 5. Shared CI for the infrastructure

infra holds the reusable workflows (`workflow_call`) and the Renovate presets. homelab and the service repositories call each workflow at a tag (dan-petty/infra#4).

### 6. infra holds no private data

infra is public. It never holds the real domain, a host or node name, a private address, a device path, an inventory, a Secret or a token. Templates and tests use `<domain>`, `example.com` and RFC 5737 addresses. The CI of infra refuses each of these values (dan-petty/infra#4).

### 7. A service onboards with one services entry

A service repository onboards to the cluster with one services entry in the environment repository, and with no code in the platform. #6675 records how a service gets its Secrets.

### 8. Amendments

- **ADR 0026, decision 1.** The shared module moves to infra as `tf/modules/github-repository`. The root stacks go to dan-petty/homelab `tf/github/` (owner decision of 2026-11-21), because they name private repositories.
- **ADR 0027.** The self-hosted Renovate leaves `k8s/devops`. A later change removes its manifests from devops-cli, and homelab then runs Renovate from the upstream renovatebot chart. That chart is AGPL-3.0, so the license exception of ADR 0027 also covers the unmodified upstream chart.

### 9. Sequence with #5134

Before plan step 12 (freeze and soak) of #5134 and dan-petty/homelab#38, no file of the #5134 copy changes in homelab, and no homelab Application is added. No node change runs during plan steps 10 to 12. This record does not change the copy set.

### Consequences

- Good, because one rule tells a reader where each template is, and a new service needs only its entry.
- Good, because a consumer takes a shared change only when Renovate proposes a new tag.
- Bad, because a shared change takes one pull request in infra and then one in each consumer.
- Bad, because the roadmap does not enforce a blocker in another repository, so a person orders the work across repositories.
- Bad, because the license exception of ADR 0027 grows from one image to the upstream chart.

### Confirmation

The private-data check of the infra CI refuses a private value in infra (dan-petty/infra#4). The `domain` row of `devops ci` refuses the real domain in devops-cli. The Renovate fixture of dan-petty/infra#6 extracts one pin of each form.

## More Information

- The plan items: dan-petty/infra#4, dan-petty/infra#5, dan-petty/infra#6, #6676, #6677, dan-petty/homelab#74 and dan-petty/danielpetty.com#39.
- The Argo CD page: [best practices](https://argo-cd.readthedocs.io/en/stable/user-guide/best_practices/).
- The change: `openspec/changes/archive/2026-11-21-6674-four-homes-adr/`.

## Status History

2026-11-21: Accepted by the owner, the merge of #6683.
2026-11-27: Fact out of date: sections 1, 3 and 5, dan-petty/github-workflows holds the reusable workflows and the repository template, and releases them with its own tags (dan-petty/infra#217, #7482).
