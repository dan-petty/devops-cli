# Design

## Decisions

- **Grace period of the gateway pod: 600 s.** The issue gives this value. It covers a normal long call, and it is shorter than the router timeout of 1500 s, which is the upper limit. The Deployment keeps the default rolling update, so the new pod starts and becomes ready before Kubernetes stops the old pod. The longer grace period only lets the old pod finish its calls and write its spend queue, and the Service has a ready pod all the time. A check fails when the grace period is not 600, when it is not shorter than the router timeout, or when the strategy is not a rolling update: with `Recreate`, the new pod would wait for the old pod for up to 600 s.
- **No preStop hook.** Uvicorn starts the drain on SIGTERM, as in the roadmap Service (`k8s/devops/roadmap-service/deployment.yaml`). The evidence shows cut calls after 30 s, and no refused connection at the start of a stop.
- **Smart shutdown of the database: 15 s.** The issue gives this value. The idle sessions of the old gateway pod are the only sessions that held the smart shutdown open, and the fast shutdown closes them. 15 s is much shorter than the window in which the new gateway pod tries its migration check 4 times and stops, plus the kubelet back-off. The fast shutdown keeps the rest of `stopDelay` (1800 s), so a check also holds `smartShutdownTimeout` below `stopDelay`: when it is not below, CloudNativePG ignores the smart shutdown.
- **Probe timeout of the gateway: 5 s on all three probes.** The startup probe calls the same path on the same uvicorn worker, so the same rule applies to it. 5 s is shorter than the period of each probe (10 s and 15 s). The startup window stays `periodSeconds` 10 times `failureThreshold` 60, so a migrating pod still has ten minutes.
- **`allow_requests_on_db_unavailable` stays unset.** The existing check `check_the_gateway_refuses_a_key_it_cannot_check_when_the_database_is_down` holds it.
- **The checks are in the `k8s` row**, in `tests/gate/k8s_checks/gateway_database.py`, beside the other checks of the gateway probes. A check of committed manifests is a row of `devops ci` (docs/TESTING.md).
- **Two images, two pull requests.** `.github/renovate.json` has no group for the PostgreSQL image or the LiteLLM image, so Renovate opens one pull request for each. `k8s/README.md` tells a person to change them in different pull requests too.

## Rejected alternatives

- **Grace period of 1500 s (the router timeout) or 1100 s (the `devops-background` timeout).** The issue gives 600 s, which covers the calls that were cut. A longer value makes each node drain and each stop of a hung pod wait longer, for calls that are rare.
- **`allow_requests_on_db_unavailable: true`.** The gateway is reachable from outside the cluster, so a key that it cannot check while the database is down must be refused (`k8s/llm/gateway/config.yaml`).
- **`smartShutdownTimeout: 0`.** CloudNativePG then goes directly to a fast shutdown, and an open write of the spend queue has no time to commit. 15 s keeps a short window for it.
- **A pod-level fix in LiteLLM, such as `timeout_graceful_shutdown` or a retry delay of the migration check.** LiteLLM v1.103.11 gives no option for either, and the Kubernetes and CloudNativePG fields cover the need.
- **A second replica of the gateway.** It does not stop the cut of calls on the stopped pod, and the gateway runs one replica by design.
