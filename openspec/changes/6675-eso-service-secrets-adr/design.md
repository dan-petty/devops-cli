# Design

## Decisions

- **Record the choice in an architecture decision record, MADR 4 form.**: The choice is difficult to reverse: it adds an operator to the cluster and fixes where each service value comes from.
- **Two paths for cluster Secrets.**: ESO makes each service Secret, and `devops k8s push-secrets` keeps the platform Secrets, so no row of one service goes into the platform (ADR 0032, section 2).
- **The ESO Kubernetes provider and one store namespace for each service.**: The store is a namespace of the same cluster, so no new secret service runs. A store reads every Secret of its namespace, so each service gets its own store namespace (dan-petty/infra#12).
- **The remote key `<namespace>.<secret>`.**: Two `PushSecret` objects with one remote key and `updatePolicy: IfNotExists` write one remote Secret. The prefix stops two namespaces of one service from sharing a value by accident.
- **A `Password` generator and a `PushSecret` with `updatePolicy: IfNotExists` and `deletionPolicy: None`.**: The generator makes a new value at each refresh. The push keeps only the first value, and the value stays when the `PushSecret` goes.
- **The owner decision of 2026-11-21 is decision text.**: The owner approved the cluster-wide ESO, counted a generated value after a person merge as a person change of a Secret, and kept a typed value for a person only (#6675).
- **A sync wave orders the service objects before the reader.**: Argo CD applies a wave only when the earlier waves are healthy, and its built-in health checks read the `Ready` condition of an `ExternalSecret` and a `PushSecret`.
- **ADR 0032 gets its accepted status in this change.**: The merge of #6683 by the owner accepted it, and the README allows a status key, the `body-hash` and one dated `Status History` line. The line follows the form `Accepted by the owner, ...` of ADR 0028 and ADR 0029.

## Rejected alternatives

- **Sealed Secrets**: it has no generator, it keeps ciphertext in git against CF4, and one vendor keeps it.
- **SOPS with KSOPS in Argo CD**: the repo-server holds the key, and the Argo CD page on secret management says that the cache holds the secrets that manifest generation injects.
- **A push-secrets table in each service repository**: home-grown code that duplicates ESO (AGENTS.md rule 3).
- **A row of `cluster_secrets.py` for each service Secret**: ADR 0032, section 2, forbids a row of one service in the platform.
