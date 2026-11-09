# Design

## Decisions

- **Record the query in `k8s/README.md` and hold it with a test in `tests/prometheus/test_k8s_monitoring_alerting.py`.**: That module already reads a runbook section with `tests/prometheus/test_k8s_monitoring_alerting.py:1282:def _readme_section(heading: str) -> str:`, and `k8s/README.md:185:removes the models that no tier of a node serves` is where the runbook documents the prune.
- **Divide the available bytes by the size bytes over a `[7d]` range and select a ratio below `0.25`.**: node-exporter serves both series for the root filesystem, as the existing rule shows at `k8s/monitoring/prometheus-values.yaml:303:node_filesystem_avail_bytes{mountpoint="/"}`, and a byte count alone states no 25% bound.
- **Match one node with `instance` and write the node as `<node>`.**: Each node has its own root filesystem and its own model store, so a query with no `instance` matcher mixes the nodes and hides a full one behind the others.
- **Place the new `###` section between the disk-rule paragraph of Alerting and `### Receiver`.**: `_readme_section` ends a section at the next `###` (`tests/prometheus/test_k8s_monitoring_alerting.py:1286:end = text.find(`), so the section stays bounded at `k8s/README.md:520:### Receiver`, and the disk rules are described in that part of Alerting.
- **Leave the 7-day measurement and the comment on #3654 to #4001 and to a person.**: The measurement waits on the live node and 7 days of samples, which no pull request delivers, and #4001 is the open split that asks for the live ratio and the comment.
- **Add no spec delta.**: The change edits a document and a test and alters no behavior that a consumer observes; no command, option or message of `devops` changes.

## Rejected alternatives

- **Record the query only in a comment on #3654.**: The next prune would have no method to repeat; `k8s/README.md:185:removes the models that no tier of a node serves` is where the runbook documents the prune.
- **Use `node_filesystem_avail_bytes` alone with a byte threshold.**: It is a byte count, so no threshold states 25% of the filesystem; the tree divides it by the size series at `k8s/monitoring/prometheus-values.yaml:303:node_filesystem_avail_bytes{mountpoint="/"}`.
- **Take `LocalPathNodeDiskHigh` as proof of the 25% bound.**: It fires at 85% used, 10 points above 75%, and only after 15 minutes: `k8s/README.md:481:is over 85% used, where the kubelet starts to delete unused images` with `k8s/monitoring/prometheus-values.yaml:317:for: 15m`.
- **Lower `LocalPathNodeDiskHigh` to 75%.**: 85% is where the kubelet starts image garbage collection: `k8s/README.md:387:At 85% the kubelet starts to delete unused images.` states the limit of the node.
- **Place the section after `### Planned maintenance`.**: `_readme_section` ends a section at the next `###` (`tests/prometheus/test_k8s_monitoring_alerting.py:1286:end = text.find(`), and no `###` follows `k8s/README.md:538:### Planned maintenance` before `k8s/README.md:563:## Cluster Secrets`, so the section would run on and the guard would match text outside it.
- **Run the 7-day measurement in this pull request.**: The 7 days of samples follow the prune on the live node, which the `read_issue` for #3654 showed closed and released in v0.82.0, so #4001 holds the measurement and the comment.

## Security

The new section of `k8s/README.md` crosses no trust boundary: it publishes a PromQL query and a read-only `kubectl -n llm exec <tier-pod> -- ollama list` command, and it holds no secret, no credential and no host address. A person must confirm that the section names the node only through the placeholder `<node>`, and that it adds no private address, internal host name or private registry. `tests/invariants/test_committed_addresses.py` fails on a private address or a `.lan` host in a committed file, and the new test in `tests/prometheus/test_k8s_monitoring_alerting.py` fails when the section loses a part of the query.
