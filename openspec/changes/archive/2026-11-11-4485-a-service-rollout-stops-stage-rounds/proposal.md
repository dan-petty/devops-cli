# Proposal

## Why

Issue #4485: a rollout of `roadmap-service` stops the stage and refine rounds in flight, and the stopped round writes no record.

On SIGTERM, `ServiceManager.drain_and_stop` waited `service.drain_timeout_seconds` (120 s) for the workers. During that wait a worker started the rounds of the pending triggers, a round started its next row, and the stage and refine rows started their next item. Nothing ended the round in flight: `RequestBudget.close()` refuses only a request that waits for a full window, so the stop error of #2753 almost never came. After 120 s the process exited. The model work of the item in progress was lost, and a GitHub request in flight failed with "The GitHub session closed before ... was answered", which the row counted as a failure. The pod's grace period was 150 s.

The Service shut down 69 times in the 4 days to 2026-11-11. In each sample, "Application shutdown complete." came exactly 120 s after "Waiting for application shutdown.", so a round was still in flight. The 14-day study counted 53 of 71 restarts since 2026-11-07 (75%) that stopped a running stage round, and about 146M tokens a week in the 10 minutes before a shutdown.

## What Changes

- On SIGTERM the Service stops in two bounded phases. First no worker starts a round, no round starts a row, and the stage and refine rows start no next item. The rounds in flight get `CONST_SERVICE_STOP_DRAIN_SECONDS` (600 s) to end. Then the request budget refuses every GitHub request (`RequestBudget.cut`), so a round still in flight ends at its next request through the stop path of #2753 within `CONST_SERVICE_STOP_CUT_SECONDS` (30 s).
- A round that the stop ends writes the items it did, counts no failed round, and leaves the items and rows it did not start to the next pod. A row that did not start counts no job and stays due.
- A new module, `roadmap/service_stop.py`, holds the process-wide stop that the drain sets and that the row loop and the stage and refine item loops read.
- The setting `service.drain_timeout_seconds` and `DEFAULT_SERVICE_DRAIN_TIMEOUT_SECONDS` are removed. The two waits are constants, because the grace period of the pod in `k8s/devops/roadmap-service/deployment.yaml` must cover them, and a manifest cannot follow a setting. `ServiceConfig` ignores an unknown key, so a config file or a live ConfigMap that still holds the key loads.
- `terminationGracePeriodSeconds` goes from 150 to 660 (`CONST_SERVICE_STOP_GRACE_SECONDS`). The pod has no preStop hook: uvicorn starts the drain on SIGTERM.
- The stop is a behavior of the Service that a consumer observes, so the change carries a spec delta.

## Capabilities

### Modified Capabilities

- `roadmap-service-limits`: no new work starts once the Service stops, and the stop drains in two bounded phases.

## Impact

- `src/devops_cli/roadmap/service_stop.py` (new), `src/devops_cli/server/service.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/stage/stage.py` (`_plan_each` only), `src/devops_cli/roadmap/refine/refine.py` (`plan_refine` only)
- `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/k8s/configmap.py`, `src/devops_cli/lang/en/messages.py`
- `k8s/devops/roadmap-service/deployment.yaml`, `k8s/README.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`
- Tests under `tests/server/`, `tests/github/`, `tests/roadmap/`, `tests/k8s/`, `tests/commands/`, `tests/security/`
- The change fits one pull request.

## Feasibility

- **The drain today.** `drain_and_stop` (`src/devops_cli/server/service.py`, origin/main at 54743c44) sets the stop event, calls `budget.close()`, and calls `worker.wait_active(remaining)` for each worker. `wait_active` waits while the worker is active or has a runnable batch, and `_wait_for_next_batch` pops a runnable batch even when the stop is set. So the drain starts new rounds.
- **The stop error today.** `RequestBudget.admit` raises `ServiceStoppingError` only when the window has no room and the budget is closed. The stop path that writes the items done and counts no failure exists (`StageWriter._recording`, `_run_refine_adapter`, `_count_failure`), and the tests of #2753, #3631 and #4034 cover it.
- **The exit.** The pod log of 2026-11-11 01:25:52 to 01:27:53 shows "Shutting down", "Waiting for application shutdown." and, 120 s later, "Application shutdown complete." with no end line of a round. The worker threads are daemon threads, so they stop with the process. The GitHub transport closes in a `weakref.finalize` at exit, and `unread_after_close` raises `GitHubUnreadError` for a request in flight: Loki holds 18 such lines in 14 days.
- **Probes during the drain.** The liveness probe (10 s period, threshold 3) did not end a 120 s drain in any sample, so the kubelet (k3s v1.37.2) does not restart a terminating pod for its probe.
- **The wait.** Prometheus `devops_cli_roadmap_step_seconds{row="stage",step="plan"}` over 14 days: 403 steps, mean 299 s, 30% within 150 s, 60% within 300 s, 91% within 600 s, 96% within 750 s, 98% within 900 s, 99.5% within 1200 s. The time left of the item that a stop falls in is longer than W for a share E[(D-W)+]/E[D] of stops: about 7% for 600 s and 2% for 900 s. 600 s keeps a rollout or a node drain under 11 minutes. The refine row: p90 27 s, p95 376 s.
- **The manifest.** Argo CD Application `devops` applies `k8s/overlays/homelab/devops` from `main` with automated sync, so the new grace period reaches the cluster with the merge, and the new code with the next image.

## Existing Tool Considered

Kubernetes' `terminationGracePeriodSeconds` and uvicorn's lifespan shutdown on SIGTERM do the stop; the change only sets the grace period and makes the drain use it. The process-wide stop is a `threading.Event` of the standard library, as the request gate of the budget already is. An Argo CD sync window on the AppProject can batch rollouts, but it delays every sync of the Application, self-heal included, and with the drain a rollout no longer stops a round, so it is not part of this change. The change deletes the setting `service.drain_timeout_seconds`, its default, its ConfigMap key and its tests.
