# Proposal

## Why

Issue #1322 completes Phase E test migration for the `k8s` package. The 18 test files previously coupled to internal implementation details, containing internal monkeypatches, mocks, and private imports. This change routes tests through the public interfaces and edge fakes (`cluster`, `process_fake`, `stub_web`, `keyring_store`, `clock`, and `cli`), removes internal patches, and cleans up private couplings.

## What Changes

- `apply_configured_k8s_context` moves from a private helper in `commands/devcontainer.py` to a public function in `k8s/context.py`, and `commands/devcontainer.py` calls it.
- `service_proxy.py` and `doctor.py` route Kubernetes client access through the #1315 seam (`KubernetesService`).
- Internal patches to `_kube_configuration`, `get_k8s_client`, `run_subprocess`, `subprocess.run`, `load_settings`, and `time.sleep` are removed across `tests/k8s/`.
- Private functions (`parse_kyverno_output`, `parse_opa_output`, `parse_text_falco_alert`, `tally_severity_counts`, `get_severity_color`, `sort_findings`, `transport_key`) are made public and exported in their module `__all__`.
- `_build_pods_table` unit tests and CLI pods tests move to CLI command tests under `tests/commands/k8s/`.
- `test_k8s_push_secrets.py` splits by behaviour into `test_cluster_secret_push.py` and `test_cluster_secret_plan.py`, and manifest invariant tests move to `tests/invariants/test_k8s_manifests.py`.
- Shared `http/pool.py` unit tests in `test_http_connection_pool.py` move to `tests/http/test_http_connection_pool.py`.
- FastMCP tool tests in `test_k8s_security_stream.py` move to `tests/ai/mcp/test_fastmcp_contracts.py`.
- Test names ending in `_success`, `_failure`, `_basic`, or `_command` are renamed in ASD-STE100 style.
- Rendered templates and Kustomize patches use Syrupy snapshot assertions.
- Module-level `runner = CliRunner()` instances are replaced with the `cli` fixture.
- Cache expiry tests use the #1320 `clock` fake without `time.sleep` or setting `_cache_ttl`.
- This change alters no consumer-observed CLI behavior or commands, so it sets `skip_specs: true`.
- This change fits one pull request.

## Feasibility

- `KubernetesService` provides `core_api(context)` and `configuration(context)` routing to `FakeCluster` or `KubernetesClientSource`.
- `tests/support/fakes/process.py` provides `ProcessFake` with argv scripting and automatic `shutil.which` isolation.
- `tests/support/fakes/clock.py` provides `ClockFake` backed by `time-machine` for fast, deterministic time advance.
- `tests/support/fakes/keyring.py` provides `FakeKeyring` for secret storage.
- Syrupy snapshots and Hypothesis are supported by the repository harness.

## Existing Tool Considered

- `FakeCluster` from #1315 covers the Kubernetes API seam.
- `ProcessFake` from #775 covers the subprocess boundary.
- `FakeKeyring` from #1318 covers the credential keyring boundary.
- `ClockFake` from #1320 covers time advancement and waits.
- Building custom test doubles would increase token and maintenance cost. Reusing shared fakes guarantees consistency and speed.
