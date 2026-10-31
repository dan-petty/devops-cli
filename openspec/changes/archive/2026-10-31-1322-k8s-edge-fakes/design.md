# Design

## Context

Issue #1322 completes Phase E migration for `k8s/` tests. Tests historically patched private internals, loaded local SDK clients, bypassed edge seams, and used real sleeps. This change routes tests through explicit edge seams and fakes established in Phases A through D.

## Decisions

### 1. Route Kubernetes API through `KubernetesService` (#1315)

- In `src/devops_cli/k8s/doctor.py`, `get_k8s_client(context)` returns `KubernetesService.get_instance().core_api(context=context)`.
- In `src/devops_cli/k8s/api.py`, `KubernetesApis` holds `configuration: Any = None`, supplied by `api_client.configuration` in `KubernetesClientSource` and by `FakeCluster` in tests.
- In `src/devops_cli/k8s/service.py`, `KubernetesService.configuration(context)` accesses the configuration from the active `KubernetesApis`.
- In `src/devops_cli/k8s/service_proxy.py`, `resolve_proxy_target` resolves configuration from `KubernetesService.get_instance().configuration(context)` without invoking `load_kube_config` or `load_incluster_config`.

### 2. Logic migration from `commands/` into `k8s/` (Q19)

- `apply_configured_k8s_context(*, dry_run: bool = False) -> list[str]` moves from `commands/devcontainer.py` to `src/devops_cli/k8s/context.py` and is exported in `__all__`.
- `commands/devcontainer.py` imports and invokes `apply_configured_k8s_context`.
- Tests for `apply_configured_k8s_context` run in `tests/k8s/test_k8s_context_resolution.py` using `process_fake`.

### 3. Subprocess execution via `process_fake` (#775)

- Subprocess calls across `test_k8s_chaos_runner.py`, `test_k8s_logs_diff_chaos.py`, `test_k8s_policy.py`, `test_k8s_template.py`, and `test_cluster_secret_*.py` route through `process_fake`.
- `shutil.which` checks resolve via `process_fake` rather than patching `shutil.which`.

### 4. Behaviour file splits and manifest invariants

- Manifest invariants from `test_k8s_push_secrets.py` and application override rendering from `test_k8s_argocd_overrides.py` move into `tests/invariants/test_k8s_manifests.py`.
- `test_k8s_push_secrets.py` splits into `tests/k8s/test_cluster_secret_push.py` and `tests/k8s/test_cluster_secret_plan.py`.
- Pure HTTP pool tests move to `tests/http/test_http_connection_pool.py`.

### 5. Deterministic clock via `clock` fake (#1320)

- `tests/k8s/test_k8s_service.py` uses `clock: ClockFake` to test cache expiry without setting `_cache_ttl` or calling `time.sleep`.

### 6. Snapshots and ASD-STE100 test names

- `tests/k8s/test_k8s_template.py` and `tests/k8s/test_k8s_argocd_overrides.py` use Syrupy snapshot assertions.
- Non-standard test name suffixes (`_success`, `_failure`, `_basic`, `_command`) are renamed to descriptive ASD-STE100 verb phrases.

## Rejected Alternatives

- Preserving private helper monkeypatching in tests: Rejected because it couples tests to implementation details rather than public contracts.
- Keeping `_apply_configured_k8s_context` in `commands/devcontainer.py`: Rejected by architectural requirement Q19 which dictates domain logic must reside in `k8s/`.
