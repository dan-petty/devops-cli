# Proposal

## Why

The owner decision of #741 makes `devops k8s push-secrets` write each cluster Secret from the keyring, and each Secret is a row in `src/devops_cli/k8s/cluster_secrets.py`. So a Secret of a service needs a row in product code: #6642, #6645, #6648 and #6649 planned 7 rows of one site. ADR 0032, section 2, forbids a row of one service in the platform. No decision record says how a service gets its Secrets (#6675).

ADR 0032 merged with `status: proposed` and no `body-hash`, although the merge of #6683 by the owner accepted it (`docs/adr/README.md`, Approval step 3).

## What Changes

- A new architecture decision record, `docs/adr/0033-service-secrets-come-from-external-secrets-operator.md`. It records two paths for cluster Secrets: the External Secrets Operator (ESO) with the Kubernetes provider for service Secrets, and `devops k8s push-secrets` for platform Secrets. It records one store namespace for each service, the remote key rule, the `Password` generator with a `PushSecret` that never changes a value, the typed value that only a person writes, the offline copy of a value that must never change, and the sync-wave order.
- The record writes the owner decision of 2026-11-21 as decision text: the cluster-wide ESO is approved beside the decision of #741, a value that a `Password` generator makes after a person merges the pull request that declares it is a person change of a Secret, and a typed value comes only from a person.
- CF4 and CF5 of `docs/SERVICE_PATTERNS.md`, principle 1 of `SECURITY.md` and ACC-1 of `docs/guidelines/production-readiness.md` name the `ExternalSecret` path of a service Secret. ACC-1 said that each Secret of a workload comes from push-secrets, so the record makes it wrong (AGENTS.md rule 8).
- ADR 0032 gets `status: accepted`, its `body-hash` and a dated `Status History` line that says the merge of #6683 accepted it. Its body does not change.
- The index of `docs/adr/README.md` gains the row of ADR 0033 and the new status of ADR 0032.
- The change writes no code and alters no behavior a consumer observes, so it carries no spec delta and sets `skip_specs: true`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The record and the rules are documentation, so the change carries no spec delta.

## Impact

- Documents: `docs/adr/0033-service-secrets-come-from-external-secrets-operator.md` (new), `docs/adr/0032-infrastructure-templates-live-in-four-homes.md`, `docs/adr/README.md`, `docs/SERVICE_PATTERNS.md`, `SECURITY.md`, `docs/guidelines/production-readiness.md`

## Feasibility

- The premise holds at main 52126dbd4. `src/devops_cli/k8s/cluster_secrets.py` holds the Secret rows. `docs/SERVICE_PATTERNS.md:121` (CF4) says that push-secrets writes each Secret and only a person changes a Secret, and `:122` (CF5) says that a new Secret is in the cluster before the merge of its manifest. No record in `docs/adr/` covers service Secrets.
- A read-only `kubectl get crd -o name` lists 97 CRDs, and 0 of them are of ESO, Sealed Secrets or SOPS.
- ESO: the repository `external-secrets/external-secrets` has the license Apache-2.0, and the CNCF landscape lists it as `project: sandbox`. Release `helm-chart-2.15.0` is of 2026-11-10. At tag v2.15.0, `docs/provider/kubernetes.md` documents the Kubernetes provider and its `PushSecret` support, and `docs/api/generator/password.md` documents the `Password` generator. `apis/externalsecrets/v1alpha1/pushsecret_types.go` defines `updatePolicy` `Replace` or `IfNotExists` (default `Replace`), `deletionPolicy` `Delete` or `None`, and a `generatorRef` source. `apis/externalsecrets/v1/externalsecret_types.go` gives `creationPolicy` the default `Owner`, which sets `.metadata.ownerReferences` to the `ExternalSecret`.
- Argo CD v3.6.2: `resource_customizations/external-secrets.io/ExternalSecret/health.lua` and `PushSecret/health.lua` exist, and each is `Healthy` on the condition `Ready=True`. `docs/operator-manual/secret-management.md` "strongly recommend[s]" the operators that make the Secret in the destination cluster, and "strongly caution[s]" against injection at manifest generation, because the cache holds the injected secrets. `docs/user-guide/orphaned-resources.md` names only a top-level resource as orphaned, so a Secret with an owner reference is not orphaned. `docs/user-guide/sync-waves.md` applies a wave only when the earlier waves are in sync and healthy.
- The plan items exist and are open: dan-petty/infra#12 (the ESO templates and the tenant store), dan-petty/homelab#82 (install ESO), dan-petty/homelab#96 and #6685 (the platform Secret rows move to homelab data).
- The form rules are those of `docs/adr/README.md`, checked by `tests/invariants/test_adr_records.py`, and `uv run devops docs generate` writes the index. The README allows a change of the status key and one dated `Status History` line on ADR 0032. `body-hash` is a front-matter key that the test calculates from the body.
- The ADR budget of the alternatives check is 8,192 tokens (`CONST_ROADMAP_ALTERNATIVES_MAX_ADR_TOKENS`), and it was full before this change: at main 52126dbd4, `fit_to_budget` keeps 23 of the 25 records in force and leaves out ADR 0001 and ADR 0004. With ADR 0032 accepted and ADR 0033 added, it keeps 26 of 27 records (8,184 tokens) and leaves out ADR 0005. ADR 0033 supersedes no record, so its option bullets are short. #5049 holds the fix of the budget.

## Existing Tool Considered

The decision uses the External Secrets Operator, an open, maintained CNCF Sandbox project, with its Kubernetes provider, its `Password` generator and its `PushSecret`, and the built-in health checks of Argo CD. It replaces the plan of a push-secrets row for each service Secret, so the planned rows of #6642, #6645, #6648 and #6649 are not built. The record itself needs no tool: MADR 4 is the form, and the repository already holds the records and their check (`src/devops_cli/docs/adr_records.py`). The change deletes no internal code.

## Dependencies

- ADR 0032, in `docs/adr/`, done (#6674).
- Owner decision of 2026-11-21 (#6675): the cluster-wide ESO is approved as the path of service Secrets beside the decision of #741, push-secrets stays the path of the platform Secrets, a generated value after a person merge is a person change of a Secret, and a typed value comes only from a person.
