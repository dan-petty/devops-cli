---
status: accepted
date: 2026-11-21
decision-makers: [owner]
issue: 6675
body-hash: "6215f8770335e224d0eea3b04161d9b8285c334e9c625fa171a994d2be9e039e"
---

# Service Secrets come from External Secrets Operator

## Context and Problem Statement

The owner decision of #741 makes `devops k8s push-secrets` write each cluster Secret from the keyring, and each Secret is a row in `src/devops_cli/k8s/cluster_secrets.py`. So a Secret of a service needs a row in product code: #6642, #6645, #6648 and #6649 planned 7 rows of one site. [ADR 0032](0032-infrastructure-templates-live-in-four-homes.md), section 2, forbids a row of one service in the platform. On 2026-11-21, 0 of the 97 CRDs of the cluster are of External Secrets Operator (ESO), Sealed Secrets or SOPS, and no record says how a service gets its Secrets.

## Decision Drivers

- A new service repository needs no code, row or constant in the platform.
- No secret value goes into git, also as ciphertext.
- The [Argo CD page on secret management](https://argo-cd.readthedocs.io/en/stable/operator-manual/secret-management/) "strongly recommend[s]" an operator that makes the Secret in the destination cluster. It "strongly caution[s]" against injection at manifest generation, because the cache holds the injected secrets.
- Only a person sets a value.
- An open, maintained tool comes before home-grown code (AGENTS.md rule 3).

## Considered Options

- **ESO with the Kubernetes provider**: chosen.
- **Sealed Secrets**: rejected, because it has no generator and keeps ciphertext in git.
- **SOPS with KSOPS**: rejected, because the repo-server holds the key and the cache holds plaintext.
- **A push-secrets table in each service repository**: rejected, because it duplicates ESO.
- **A push-secrets row for each service Secret**: rejected, because the platform then holds service rows.

## Decision Outcome

Chosen option: "ESO with the Kubernetes provider", because ESO makes each Secret in the cluster from objects that hold no value, with no code and no row in the platform.

### 1. Two paths for cluster Secrets

- **A service Secret** comes from ESO. The owner approved the cluster-wide ESO on 2026-11-21 as the path of service Secrets, beside the decision of #741.
- **A platform Secret**, such as a Secret of a stack in `k8s/`, stays on `devops k8s push-secrets`, and the keyring stays its store. Its row definitions move to homelab data later (dan-petty/homelab#96, #6685).

### 2. One store namespace for each service

- ESO runs one time in the cluster, from its upstream chart (Apache-2.0, a CNCF Sandbox project). dan-petty/infra holds its general values (dan-petty/infra#12), and dan-petty/homelab installs it (dan-petty/homelab#82).
- Each service gets one store namespace, `<name>-secrets`. The tenant chart of dan-petty/infra makes a `SecretStore` with the Kubernetes provider in each namespace of the service, and each store reads only the store namespace of its service (dan-petty/infra#12).
- The service repository holds only `ExternalSecret`, `PushSecret` and `Password` objects. Its AppProject allows no `Secret`, no `SecretStore` and no other generator. So a service cannot read the Secrets of another service or send a value out.
- A remote key in a store namespace starts with its source namespace: `<namespace>.<secret>`. So two namespaces of one service never share a value by accident.

### 3. Where a value comes from

- **A value that nobody types** comes from a `Password` generator. A `PushSecret` with `updatePolicy: IfNotExists` and `deletionPolicy: None` writes it one time into the store namespace. So the value never changes, and it stays when the `PushSecret` is deleted. An `ExternalSecret` reads it back. A value that the generator makes after a person merges the pull request that declares it is a person change of a Secret (owner decision of 2026-11-21).
- **A typed value** comes only from a person. The person writes it into the store namespace with `kubectl -n <name>-secrets create secret generic <namespace>.<secret> --from-file=<key>=/dev/stdin`. No value goes into git.
- **A value that must never change**, such as an encryption key or a restic password, also gets an offline copy that the owner keeps.

### 4. Order and health

- A sync wave puts the `Password`, the `PushSecret` and the `ExternalSecret` before the object that reads the Secret. Argo CD applies a wave only when the earlier waves are healthy, and it has built-in health checks for `ExternalSecret` and `PushSecret`. So a generated value needs no person push before the merge.
- A typed value is in the store namespace before the merge of the `ExternalSecret` that reads it.
- A Secret that ESO makes has an owner reference to its `ExternalSecret` (`creationPolicy: Owner`, the default). So Argo CD does not show it as orphaned, and the AppProject needs no orphan ignore for it.

### Consequences

- Good, because a new service gets its Secrets with no code, row or constant in the platform.
- Good, because a generated value needs no person step, and no value is in git or in the Argo CD cache.
- Good, because ESO is an open, maintained operator, and Argo CD knows its health.
- Bad, because the cluster runs one more operator, with an admission webhook and large CRDs.
- Bad, because the cluster has two paths for Secrets.
- Bad, because a generated value is only in the cluster, so a value that must never change needs the offline copy of the owner.

### Confirmation

- `kubectl get externalsecret -A` shows the reason `SecretSynced` for each `ExternalSecret` of a service, and Argo CD shows each service Application `Healthy`.
- The unit tests of the tenant chart (dan-petty/infra#12) show that the AppProject of a service allows `Password` and no other generator, and no `SecretStore`.
- Gitleaks and `trivy config` in the Security Scan step of CI refuse a secret value in git.

## More Information

- The rules: CF4 and CF5 of [SERVICE_PATTERNS.md](../SERVICE_PATTERNS.md#8-configuration-and-secrets), principle 1 of [SECURITY.md](../../SECURITY.md), ACC-1 of the [production readiness guideline](../guidelines/production-readiness.md#access-and-secrets).
- The plan items: dan-petty/infra#12, dan-petty/homelab#82, dan-petty/homelab#96 and #6685.
- The ESO pages: [Kubernetes provider](https://external-secrets.io/latest/provider/kubernetes/), [Password generator](https://external-secrets.io/latest/api/generator/password/), [PushSecret](https://external-secrets.io/latest/api/pushsecret/).
- The change: `openspec/changes/archive/2026-11-21-6675-eso-service-secrets-adr/`.
