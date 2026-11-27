# Design

## Decisions

- **The memory of a row is its request and its limit.** `RunnerSize.resources()` gives the same CPU and the same memory under `requests` and under `limits`. The scheduler then keeps a Job off a node with less free allocatable memory than the Job can use, and the Job cannot take memory that it did not reserve.
- **The rows come from the peaks of 14 days with the room of T1.** `docs/guidelines/kubernetes.md` (Tune down from the measured peaks, rule 2) sets the limit so that the highest peak is at most 80 % of it. Small row: 3.80 GiB / 0.8 = 4.75 GiB, so 5Gi (76 %). Large row: 8.05 GiB / 0.8 = 10.06 GiB, so 11Gi (73 %). A test holds each `peak_bytes` at most 80 % of the memory of its row.
- **Remove the setting.** Only `job_launcher.launch` read `roadmap.implement.max_memory_limit`. A setting that only checks the rows would be a second place that holds the same value.
- **The policy pins the limit to the request.** The size rule of `roadmap-service-jobs` adds `requests.memory == limits.memory` for `agent`, so a change of the code that sets another limit fails in the gate check and in the cluster.
- **`prepare` and `publish` keep the small row of the template.** Their limits (2Gi) are below the memory of `agent`, so the pod request equals the pod limit. Their row is in the template, outside the size table.

## Rejected alternatives

- **Size the rows from the peaks of the container `agent` only (3Gi and 6Gi).** The container `agent` exists since 2026-11-22 and holds 42 Jobs. In the same 14 days, 117 Jobs of the one container `runner` ran the same agent step. The large Job of #6340 on 2026-11-20 reached 8.05 GiB of working set and 7.53 GiB of RSS, which a 6Gi limit would kill.
- **A large row of 10Gi.** The peak of 8.65 GB is 80.5 % of 10Gi, above the 80 % of T1 in `docs/guidelines/kubernetes.md`.
- **Keep `roadmap.implement.max_memory_limit` as an upper bound that the validator checks against the rows.** No code reads it then, and the rows already hold the value: `git grep -n max_memory_limit -- src` named only `job_launcher.py:117` and the settings model.
- **A custom node label with a required node affinity (#5485, dan-petty/homelab#302).** The owner closed both as not planned on 2026-11-27. The request of a pod gives the same placement with no play on the nodes.
