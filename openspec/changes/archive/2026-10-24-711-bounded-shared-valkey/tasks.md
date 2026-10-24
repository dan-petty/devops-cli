# Tasks

## 1. Memory bound of the llm Valkeys

- [x] 1.1 Write a failing test that holds the cache Valkey and the run index to `--maxmemory` at most three quarters of the container memory limit and to `--maxmemory-policy noeviction`, and add the two flags to the full command of the cache Valkey (`uv run devops ci test tests/test_k8s_valkey_stack.py`).
- [x] 1.2 Start the cache Valkey in `k8s/llm/valkey.yaml` with `--maxmemory 1536mb` and `--maxmemory-policy noeviction`, with the basis of both in a manifest comment (`uv run devops ci test tests/test_k8s_valkey_stack.py`).
- [x] 1.3 Describe the bound and the policy of the cache Valkey in `k8s/README.md`, and sync the documentation with `uv run devops docs generate --sync-readme` (`uv run devops docs check`).

## Workflow follow-up

- moved to #2093, after #2095: evaluate kube-linter's `latest-tag` check, or an equal open tool, in CI. It must flag a `:latest` tag and leave an untagged image that Argo CD Image Updater pins. kube-linter 0.8.3 is in `tools.lock`, but its default `latest-tag` block list also blocks an untagged image, so the check needs a custom check from the `latest-tag` template with `.*:(latest)$` alone. `devops k8s lint` exits 0 when kube-linter finds problems, and prints "passed" when kube-linter is not installed, so CI must not run the guard through it in its current state.
- moved to #2094: alert when the cache Valkey's memory use nears its bound (`redis_memory_used_bytes` over `redis_memory_max_bytes` of its redis-exporter sidecar). With `noeviction`, a full Valkey refuses writes, and `ValkeyCacheErrors` does not cover a refused write.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
