# Proposal

## Why

The prune of #3654 frees the root disk of a node, but nothing states how to confirm that the free space stays. A later model pull fills the store again, and the kubelet deletes images at 85% used and evicts pods under DiskPressure. #3660 records the query for one node in the runbook, so the next prune has a method to repeat, and #4001 runs the 7-day measurement and the comment on #3654.

## What Changes

- Add the section `### Free space of the root disk after a prune` to `k8s/README.md`, after the disk-rule paragraph of Alerting and before `### Receiver`, with the free-space query of one node.
- State the query as `min_over_time(node_filesystem_avail_bytes{mountpoint="/", instance="<node>"}[7d]) / max_over_time(node_filesystem_size_bytes{mountpoint="/", instance="<node>"}[7d]) < 0.25`, so a result names the node that fell below 25% free and an empty result means the node stayed above it for the 7 days.
- State that Prometheus keeps 30 days of samples, so the `[7d]` window is readable, and that `LocalPathNodeDiskHigh` fires at 85% used and is no proof of the 25% bound.
- Name the `kubectl -n llm exec <tier-pod> -- ollama list` check of the models that the node keeps, against the keep table of GPU Placement.
- Name the comment on #3654 that holds the query and its result, and leave that measurement to #4001.
- Add `test_the_readme_states_the_free_space_query_of_a_node_after_a_prune` to `tests/prometheus/test_k8s_monitoring_alerting.py`, which reads the section with `_readme_section` and fails on each of the seven parts that is missing.
- Add no spec delta: the change edits a document and a test and alters no behavior that a consumer observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `k8s/README.md`
- Tests: `tests/prometheus/test_k8s_monitoring_alerting.py`

## Feasibility

- Probe, word for word: The path `k8s/README.md` is a file of the staging commit. The path `k8s/monitoring/prometheus-values.yaml` is a file of the staging commit. The path `tests/prometheus/test_k8s_monitoring_alerting.py` is a file of the staging commit. The path `CONTRIBUTING.md` is a file of the staging commit.
- Probe, word for word: The path `server.retention` is no file of the staging commit. No commit in the history deleted or renamed it. `server.retention` and `server.retentionSize` are keys, not files: the `read_file` of `k8s/monitoring/prometheus-values.yaml` lines 1-20 showed `k8s/monitoring/prometheus-values.yaml:11:retention: 30d` and `k8s/monitoring/prometheus-values.yaml:12:retentionSize: 16GB`, so Prometheus keeps the 7 days of samples that the query reads and the issue cites no deleted file.
- The `read_file` of `tests/prometheus/test_k8s_monitoring_alerting.py` lines 1250-1340 showed `tests/prometheus/test_k8s_monitoring_alerting.py:1282:def _readme_section(heading: str) -> str:` and `tests/prometheus/test_k8s_monitoring_alerting.py:1286:end = text.find(`, so the helper reads one `###` section of `k8s/README.md` up to the next `###`. This run read that file, which the earlier reply cited without the read.
- The `search_code` for `_readme_section` returned 3 hits, all in `tests/prometheus/test_k8s_monitoring_alerting.py`, at lines 1282, 1295 and 1394, so that module already holds a section of the runbook against a rule.
- The `search_code` for `LocalPathNodeDiskHigh` showed `k8s/README.md:481:is over 85% used, where the kubelet starts to delete unused images`, `k8s/README.md:387:At 85% the kubelet starts to delete unused images.` and the rule at `k8s/monitoring/prometheus-values.yaml:301:alert: LocalPathNodeDiskHigh`, so the alert fires 10 points above the 75% bound and proves nothing about it.
- The `read_file` of `k8s/monitoring/prometheus-values.yaml` lines 290-320 showed `k8s/monitoring/prometheus-values.yaml:303:node_filesystem_avail_bytes{mountpoint="/"}` with `> 0.85` and `k8s/monitoring/prometheus-values.yaml:317:for: 15m`, so both filesystem series reach Prometheus for `mountpoint="/"` and the ratio form is the one the tree already uses.
- The `read_file` of `k8s/README.md` at lines 440-500 and 500-620 showed `k8s/README.md:458:Prometheus keeps every series node-exporter serves, with no allow list`, the alert row at line 481, `k8s/README.md:520:### Receiver`, `k8s/README.md:538:### Planned maintenance` and `k8s/README.md:563:## Cluster Secrets`, so the new `###` section goes between the disk-rule paragraph and `k8s/README.md:520:### Receiver`, where `_readme_section` bounds it at the next `###`.
- The `read_file` of `k8s/README.md` lines 170-200 showed `k8s/README.md:185:removes the models that no tier of a node serves`, the keep table header `k8s/README.md:178:| Gateway target | Models it keeps |` and its guard sentence `k8s/README.md:176:fails when this table and the gateway config differ`, so the section can point at the models a node keeps.
- The `search_code` for `uv run devops ci test` showed `CONTRIBUTING.md:59:uv run devops ci test`, so the verify command is the project's targeted test command.
- The `read_issue` for #3654 showed it closed (completed) and released in v0.82.0, and the `find_issues` for `node_filesystem_avail_bytes` listed 2 open items, #3660 and #4001, so the prune is on the default branch and no other open item changes the query.
- The `read_issue` for #4001 showed it open and split from #3660, and it asks for the live ratio, the alert watch and the comment on #3654, so this plan records the query and leaves the measurement to it and to a person.
- The count of the parts that the new test guards is 7, and no tool counts them: the plan marks the count unverified, makes `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` the census command of group 1, and stops when its result differs from the plan. The parts and their decisions: `node_filesystem_avail_bytes` kept, `node_filesystem_size_bytes` kept, `mountpoint="/"` kept, `instance=` kept, `[7d]` kept, `0.25` kept and `ollama list` kept; none is removed, restricted or allowlisted.
- The test calls `_readme_section("Free space of the root disk after a prune")`, whose argument needs a checkout of the repository, because the helper reads `k8s/README.md`; it needs no client of a service and no network.
- The verify `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` runs `uv`, `devops` and `pytest`, each a runner tool of the image and none `NOT_IN_RUNNER`, and it needs a checkout of the repository, no client and no network; its failure classes are `test`, `lint` and `types`, and the pod settings `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault` apply.
- The documented `kubectl -n llm exec <tier-pod> -- ollama list` command runs on a person's workstation, and `kubectl` is `NOT_IN_RUNNER` in the image, where only the `k8s` row runs it, so no group runs it; the pod settings `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault` apply to the verify and not to that command.
- The 7-day window, the live node and the alert watch of the acceptance criteria are `not checked` by this run and cannot be delivered by a pull request: the ratio, the alert silence and the `ollama list` output need the pruned node and 7 days of samples. The plan records the query and builds no code that compensates for that wait.
- The staged tree defines no constant for the `0.25` bound or the `[7d]` range, so the section and the test write those literals and give no new name to a bound that the tree defines.
- `AGENTS.md`, `It.two`, `then.method` and `node_filesystem_free_bytes` from the probe list are `not checked` by this run, and the plan relies on none of them.
- The `list_files` of `tests/invariants` showed `tests/invariants/test_committed_addresses.py`, and the `read_file` of its lines 1-40 showed `tests/invariants/test_committed_addresses.py:1:No committed file holds a private address or an internal`, so a private address in the new section fails that test.

## Existing Tool Considered

Prometheus with node-exporter, scraped by the k8s-monitoring chart, serves `node_filesystem_avail_bytes` and `node_filesystem_size_bytes` for the root filesystem of each node and keeps 30 days of samples (`k8s/monitoring/prometheus-values.yaml:11:retention: 30d`), and `ollama list` answers the model check, so the change adopts these tools and builds no code.

## Dependencies

None.
