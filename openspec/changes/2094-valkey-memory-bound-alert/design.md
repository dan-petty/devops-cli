# Design

## The rule

```promql
redis_memory_used_bytes / redis_memory_max_bytes > 0.8
  and redis_memory_max_bytes > 0
  and on (namespace, instance) redis_instance_info{maxmemory_policy="noeviction"}
```

The rule waits 10 minutes and has the severity `warning`. The value of the alert is the ratio, so the summary shows it as a percentage.

- `redis_memory_max_bytes` is the `maxmemory` of the server. It is 0 for a server with no bound, and then the ratio is `+Inf`. The guard `redis_memory_max_bytes > 0` removes that series. Argo CD's Redis has no bound and the policy `noeviction`, so without the guard the rule fires for it all the time.
- `redis_instance_info` comes from the same scrape as the two memory gauges. It has other labels (versions, run ID), so the join matches on `namespace` and `instance` only.
- The rule keeps the labels of the scrape, as `ValkeyCacheErrors` does. The node of the pod is one of them, so a node silence also hides the alert while that node is in planned maintenance.

## Rejected alternatives

- **Select the cache Valkey by `job="valkey"`.** The issue names the cache Valkey. The cause of the failure is the policy, not the job: the run index has the same policy, and a rule by job does not cover it when it gets an exporter. The policy label is on the live series, so the rule reads it.
- **Every Valkey with a bound, with no policy join.** This is the common "out of maxmemory" alert. devops-cli's cache Valkey uses `allkeys-lru`, so at its bound it evicts a key and refuses no write. A full LRU cache is its normal state, and the alert would only add noise.
- **Add the rule to `homelab-services`.** The promtool test of a group checks that each alert of the group has a unit test. `homelab-services` has no unit tests for its eight rules, and writing them is not this item. A group of its own, after `homelab-services`, keeps the Valkey alerts together in the file and lets the new rule have its unit tests.
- **Add an exporter to the run index.** That changes a manifest, its NetworkPolicy and its scrape, which is more than the issue asks. The rule covers the run index when it gets an exporter.
