# Tasks

## 1. Implement the Valkey maxmemory ratio check

Kind: other. Reads: `tests/gate/k8s.py`, `tests/gate/k8s_render.py`, `k8s/llm/valkey.yaml`, `k8s/llm/valkey-devops.yaml`, `k8s/llm/valkey-runs.yaml`. Changes: `tests/gate/k8s_checks/valkey_memory.py`.

- [x] 1.1 Create `tests/gate/k8s_checks/valkey_memory.py` with `valkey_maxmemory_findings` and negative-control + rendered-tree `check_*` functions enforcing `--maxmemory <= 3/4 * resources.limits.memory` (`512mb` vs `512Mi` fails, `768mb` vs `1Gi` passes, omitted `--maxmemory` ignored)
  - Verification: `$ uv run devops ci --check --only k8s`

## 2. Verify all gates and code quality

Kind: other. Reads: `tests/gate/k8s_checks/valkey_memory.py`. Changes: none.

- [x] 2.1 Run `devops ci --check --skip test --force` and relevant pytest invariant checks after archiving OpenSpec change `4992-valkey-maxmemory-ratio`
  - Verification: `$ uv run devops ci --check --skip test --force`
