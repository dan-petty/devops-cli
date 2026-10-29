# Design

## Context

`loki-ingress` routes host `loki.<domain>` on the Traefik `web` entrypoint to Service `loki:3100` in namespace `logging`. The `logging-default-perimeter` NetworkPolicy admits port 3100 only from the `logging`, `monitoring` and `otel` namespaces, and from no Traefik pod. Each request therefore failed.

## Goals / Non-Goals

**Goals:**

- Remove the dead Ingress `loki-ingress`.
- Keep the `logging-default-perimeter` policy closed to Traefik.
- Add an invariant that no Ingress in the cluster targets namespace `logging`.

**Non-Goals:**

- Open the logging perimeter to Traefik.
- Enable Loki authentication as a substitute.

## Decisions

### Decision 1: Delete the Ingress and keep the policy closed

The `logging-default-perimeter` policy stays as it is, and `loki-ingress` is deleted from `k8s/ingress/ingress-routes.yaml`. Two invariant tests in `tests/invariants/test_k8s_manifests.py` fail when an Ingress names `loki-ingress`, or when an Ingress under `k8s/` has `metadata.namespace` of `logging`.

*Alternatives considered:*

- Open the policy to Traefik pods: rejected, because Loki runs with authentication disabled, so a peer for Traefik opens the Loki API to each client that reaches Traefik. #1632 recorded the decision to keep the policy closed.
- Enable Loki authentication and keep the Ingress: rejected for this pull request, because it changes the logging stack's runtime and its values, and #1632 chose to delete the Ingress instead.
