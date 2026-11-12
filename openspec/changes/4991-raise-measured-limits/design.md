# Design

## Decisions

- **Raise each memory limit to at least 1.5 times the 7 d peak.**: Grafana 2Gi is 2.0 times 1014 MiB, the gateway 4Gi is 3.1 times 1333 MiB (it grows about 170 MiB each day between rollouts), `alloy-metrics` 1536Mi is 2.1 times 737 MiB, and `alloy-logs` 768Mi is 2.2 times 342 MiB, which still rises.
- **Raise the Grafana memory request to 512Mi.**: The working set was 444 MiB at the time of the check, above the old request of 256Mi. The other requests stay, because the scheduler needs no change for them.
- **Raise the exporter CPU limits to 500m and keep the requests.**: The exporters use 2m to 33m, but CFS throttles them in 29% to 69% of the periods, so a short burst at the scrape waits for the next period. 500m lets a scrape burst finish in one period. A limit is not reserved on the node.
- **Raise the CPU limit of the Service to 2.**: The container reached 1.00 core at a limit of 1. The event loop uses one core, so the raise is for the bursts of subprocesses and native threads.
- **Do not set `MAX_REQUESTS_BEFORE_RESTART` on the gateway.**: The gateway runs one uvicorn worker in one replica, so a restart of the worker stops every model call until the container starts again. The comment above `resources` says so.
- **Keep Tempo at 2Gi.**: Its 7 d peak is 76% of the limit. The near-limit rule of #4993 watches it.
- **Hold the new values in the tests that already read these `resources` blocks.**: A later cut of a limit then fails a test.

## Rejected alternatives

- **Run KRR first and size every container from it.**: #4992 does that next. The data here already shows that these limits are too low, and Grafana is at 99% of its limit.
- **Remove the CPU limits of the exporters.**: The project sets a CPU limit on every container, and #4992 keeps that rule.
- **Raise the limits with `kubectl patch`.**: Argo CD self-heal reverts it. The live limits read the same values as git.
- **Use `MAX_REQUESTS_BEFORE_RESTART` instead of a higher gateway limit.**: With one worker and one replica, each restart fails every model call in flight.
