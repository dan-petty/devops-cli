# Tasks

## 1. The Valkey memory alert

- [x] Add failing tests: the rule pinned with its expression, wait and severity; its row in the Alerting table; the promtool unit tests of the group; the baseline rule set and the served series
  - Verification: `uv run devops ci test tests/test_k8s_monitoring_alerting.py`
- [x] Add the `valkey-memory` group with `ValkeyMemoryNearBound`
  - Verification: `uv run devops ci test tests/test_k8s_monitoring_alerting.py`
- [x] List the alert in the Alerting table of `k8s/README.md` and in the cache Valkey section, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2094-valkey-memory-bound-alert`
- Pending a person: after Argo CD syncs the merge, read the rule in Grafana's Alerting view. It stays Normal while the cache Valkey uses less than 80% of its bound.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
