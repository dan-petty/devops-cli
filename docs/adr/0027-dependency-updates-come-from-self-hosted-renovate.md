---
status: proposed
date: 2026-11-16
decision-makers: [owner]
issue: 4905
tracker: 4893
---

# Dependency updates come from self-hosted Renovate

## Context and Problem Statement

No Renovate instance ran for the 7 Service repositories: Renovate opened 0 pull requests on devops-cli from 2026-10-01 to 2026-11-12, and only security findings and persons updated the pins (#4893). The owner wants the versions to stay current with dependency management best practices. On 2026-11-11 the owner chose a self-hosted Renovate in the cluster, and accepted its license: "Self-hosted Renovate anyway".

Renovate is not permissive. The `LICENSE` file of its repository is AGPL-3.0, its `package.json` says `AGPL-3.0-only`, and the image `ghcr.io/renovatebot/renovate` has the label `org.opencontainers.image.licenses=AGPL-3.0-only`. The open-tools rule of `CONTRIBUTING.md` forbids AGPL components. Renovate also runs the `postUpgradeTasks` commands that a repository names, and its documents call that an insider-attack risk.

## Decision Drivers

- Each pin class of the Service repositories gets updates on a schedule, and a security fix comes at once.
- The updater can run the project's own commands to write locks, digests and generated documents again.
- The updater holds no key of the Service and reaches no internal service.
- A license exception stays as narrow as the need.

## Considered Options

- **Self-hosted Renovate as a plain CronJob in namespace `devops`, with its own GitHub App**: chosen.
- **The hosted Mend Renovate app**: rejected, because it cannot run the project's commands, and the owner chose self-hosted.
- **Mend Renovate Community Edition**: rejected, because it has no OSI license.
- **The Renovate Helm chart**: rejected, because it is `AGPL-3.0-only` too, it widens the exception, and it adds a chart repository to the AppProject.
- **An Argo CronWorkflow in namespace `argo-workflows`**: rejected, because that namespace allows no public HTTPS and no Secret, and an Argo pod needs egress to the API server.
- **mogenius/renovate-operator**: rejected, because a controller, a CRD and RBAC are a larger footprint than one CronJob.
- **Dependabot version updates**: rejected, because it cannot run the project's commands and has no manager for several pin classes.

## Decision Outcome

Chosen option: "Self-hosted Renovate as a plain CronJob in namespace `devops`, with its own GitHub App", because it covers every pin class, runs the project's commands, and keeps the exception on one image.

### 1. The license exception covers the unmodified image only

Renovate is AGPL-3.0-only, and the project runs the unmodified official Renovate image as a private CronJob: an accepted exception to the open-tools rule. Nobody receives a copy, and no outside user reaches it over a network, so the duty to offer the source does not start. The exception does not cover the Helm chart, a fork or a derived image. A patch to the image is a new decision.

### 2. The App key stays in the token init container

The App `dan-petty-renovate` is installed on the Service repositories only, and it has its own request budget. The init container runs `devops gh app-token --app renovate`, and only it reads Secret `devops/renovate`. Renovate reads a one-hour installation token from an emptyDir.

### 3. The Renovate pod reaches public HTTPS only

The pod runs under Pod Security `restricted` with a read-only root. Its NetworkPolicy lets it reach CoreDNS, the OTel collector and public TCP 443 only. It reaches no gateway, Valkey, Qdrant or API server.

### 4. Repository commands run only when an anchored regex allows them

`allowedCommands` holds an anchored regex for each project command, and no command runs in a shell.

### Consequences

- Good, because each pin class gets a manager, and a Dependency Dashboard shows the backlog.
- Good, because a repository command that goes wrong reaches no key and no internal service.
- Bad, because the project runs an AGPL-3.0-only image, and each patch idea needs an owner decision.
- Bad, because the cluster holds one more CronJob, one PVC and one Secret to keep.

### Confirmation

`tests/invariants/test_k8s_renovate.py` checks the Secret mounts, the timeouts, the perimeter, the anchored commands, and that this record, `CONTRIBUTING.md` and `docs/CLUSTER.md` name the same exception. The `k8s` row of `devops ci` checks the rendered image digests and the network policies.

## More Information

- The tracker: #4893. The token command: #4897. The first measured runs: #4909.
- The manifests: `k8s/devops/renovate/`. The runbook: `docs/CLUSTER.md`, section "Renovate".
- The precedent: SearXNG (AGPL-3.0) runs unmodified in the same namespace.
