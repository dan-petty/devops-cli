## ADDED Requirements

### Requirement: The k8s row rejects a Valkey bound above three quarters of its memory limit
The `k8s` gate row SHALL inspect every container running `valkey-server` across rendered environment kustomizations and report a finding naming the container, its `--maxmemory` bound, and its memory limit whenever `--maxmemory` (with `kb`/`mb`/`gb` parsed as `1024`-based bytes) exceeds three quarters of `resources.limits.memory`, while ignoring `valkey-server` containers with no `--maxmemory`.

#### Scenario: A bound above three quarters fails and exact three quarters or unbound pass
- **WHEN** `uv run devops ci --check --only k8s` runs over `tests/gate/k8s_checks/valkey_memory.py`
- **THEN** a rendered Deployment whose `valkey` container sets `--maxmemory 512mb` and limit `512Mi` produces one finding naming `valkey`, `512mb`, and `512Mi`, whereas `--maxmemory 768mb` with `1Gi` and `valkey-server` without `--maxmemory` produce zero findings and the committed tree passes
