# Tasks

## 1. Stops and probes of the gateway

Kind: behavior.

- [x] 1.1 Write the failing checks: the gateway pod sets `terminationGracePeriodSeconds: 600`, shorter than the router timeout, with a rolling update; the Cluster `llm-gateway-db` sets `smartShutdownTimeout: 15`, less than `stopDelay`; the three gateway probes set `timeoutSeconds: 5`, less than their period.
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.2 Set the three values in `k8s/llm/gateway/deployment.yaml` and `k8s/llm/gateway-db.yaml`, and keep `allow_requests_on_db_unavailable` unset.
  - Verification: `$ uv run devops ci --check --only k8s`

## 2. Documents

Kind: other.

- [x] 2.1 Tell in `k8s/README.md` how the gateway and its database stop, why the PostgreSQL image and the LiteLLM image change in different pull requests, and that a person reads spend-log rows with `/spend/logs/v2`.
  - Verification: `$ uv run devops ci --check --only docs`

## Workflow follow-up

- Pending a person: after the merge, `kubectl -n llm get cluster llm-gateway-db -o jsonpath='{.spec.smartShutdownTimeout}'` shows 15, and the instance pod of the database has the same restart count and start time as before the merge.
- Pending a person: after the merge, a rollout of the gateway during a call that is open for more than 30 s ends with `Finished server process` in the log of the old pod, and the client gets a full reply. The first rollout, at the merge, still uses the 30 s of the old pod.
- Pending a person: the next restart of the gateway database ends in less than 30 s, and the restart count of the gateway pod does not increase.
- Pending a person: a v1 `/spend/logs` call of 10,000 rows causes no `Unhealthy` probe event on the gateway.
