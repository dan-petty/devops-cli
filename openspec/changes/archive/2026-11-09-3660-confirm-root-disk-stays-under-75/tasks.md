# Tasks

## 1. Record the free-space query in the runbook and hold it with a test

Reads: `k8s/README.md`, `tests/prometheus/test_k8s_monitoring_alerting.py`. Changes: `k8s/README.md`, `tests/prometheus/test_k8s_monitoring_alerting.py`.

- [x] 1.1 Write the failing `test_the_readme_states_the_free_space_query_of_a_node_after_a_prune` in `tests/prometheus/test_k8s_monitoring_alerting.py`, after `test_each_roadmap_service_alert_points_to_its_step_in_the_readme`: it reads the section with `_readme_section("Free space of the root disk after a prune")` and asserts that the text holds each of seven parts, `node_filesystem_avail_bytes`, `node_filesystem_size_bytes`, `mountpoint="/"`, `instance=`, `[7d]`, `0.25` and `ollama list`, with a message that names the part it did not find. Then add the section `### Free space of the root disk after a prune` to `k8s/README.md`, between the disk-rule paragraph and `### Receiver`: the query `min_over_time(node_filesystem_avail_bytes{mountpoint="/", instance="<node>"}[7d]) / max_over_time(node_filesystem_size_bytes{mountpoint="/", instance="<node>"}[7d]) < 0.25`; the sentence that an empty result means the node stayed above 25% free for the 7 days and that a result names the node that fell below; the sentence that Prometheus keeps 30 days of samples and that `LocalPathNodeDiskHigh` fires at 85% used and proves nothing about the 25% bound; the `kubectl -n llm exec <tier-pod> -- ollama list` check against the keep table of GPU Placement; and the sentence that the query and its result go in a comment on #3654. Then run the census command and stop if its result differs from this plan
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes
- [x] 1.2 Edit `k8s/README.md` to add the section `### Free space of the root disk after a prune` with the query, its pass condition, the `ollama list` check and the comment on #3654
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Pending person: `node_filesystem_avail_bytes{mountpoint=`/`, instance=``}` stays above 25% for 7 days after the prune., Group 1 records the query that reports the ratio, but only a person runs it on the live node after 7 days of samples, and #4001 holds that measurement.
- Pending person: `LocalPathNodeDiskHigh` does not fire for the node in those 7 days., Only a person watches the live alert for the 7 days after the prune; the runbook already gives the rule and its 15-minute wait.
- Pending person: `ollama list` in a tier pod on the node shows each model that `k8s/README.md` says the node keeps., Only a person reads `ollama list` in a tier pod on the live node; group 1 records the command, and the keep table of GPU Placement already holds the models.
- Pending person: A comment on #3654 holds the query and the result., Only a person posts the comment on #3654 after the 7-day measurement; group 1 records the query that the comment quotes.
