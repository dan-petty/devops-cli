# Proposal: #7229

## Why

Issue #7229: some tests force a specific version or setting. Such a test fails when a dependency, a manifest, a default or an instruction text changes, although no interface changed. The update then needs an edit of a test. Of 109 dependency update commits on `main` since 2026-11-01, 19 changed a file under `src/` or `tests/`. On 2026-11-25 a change of one sentence in `src/devops_cli/templates/AGENTS.md.j2` failed a test that held the literal context size 765 (#7217).

The owner direction of 2026-11-25 is to remove each test that forces a specific version or configuration, and also the tests of this kind that guard a safety property (the gray tests).

## What Changes

- Remove 160 test functions. Ten test files go whole: `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/config/test_tuicr_config.py`, `tests/invariants/test_declared_dependencies.py`, `test_mcp_server_image.py`, `test_runner_hooks.py`, `test_runner_image.py` and `test_uv_malware_check.py`, `tests/k8s/test_k8s_argo_workflows.py`, `tests/prometheus/test_k8s_monitoring_dashboards.py` and `tests/server/routes/test_k8s_roadmap_service.py`.
- Change 33 tests that check source code and held one pinned literal. Each now compares with the constant or the setting, or with input that the test writes.
- Remove the helpers that only these tests used (68 names), the chart copy `tests/fixtures/charts/qdrant/`, one snapshot file, six `--deselect` lines of `pyproject.toml` and the duration records of the deleted files.
- Lower `tests/gate/tree_checks/config_reads.toml` to the measured counts: the tests that read a committed manifest or config file fall from 245 to 127.
- Correct the documents and the source comments that named a removed test: `SECURITY.md`, `docs/TESTING.md`, `k8s/README.md` and eight comments in seven files under `src/`.
- Two living specs named a removed test, so the change carries a delta for each. It fits in one pull request.

## Capabilities

### Modified Capabilities
- `release-concurrency-and-renovate`: the scenario of the release workflow names the two validators and no test.
- `otel-collector-alerts`: the requirement of the served series names no test.

## Impact

- A Renovate update, a change of a default, an edit of a manifest and an edit of an instruction text need no edit of a test.
- The safety properties stay in the files. No test repeats them now: the telemetry opt-outs, the permissions and triggers of named workflows, the network policies and security contexts of the manifests, the values of Argo Workflows, the safety sentences of `AGENTS.md`, the Bandit configuration and the coverage threshold of `ci.yml`. zizmor, actionlint, kube-linter, the `k8s` row, the admission policies of the cluster and the ruleset of `main` still check their form.
- No source behavior changes. Under `src/` only comments change.

## Feasibility

Confirmed in the worktree of the change:
- `uv run devops ci --check --only lint,format,test-tree,docs,typecheck,domain` passes.
- `tests.gate.tree_checks.config_values.config_reads` gives the counts of `config_reads.toml`. No count rose, and the sum is 127.
- `git grep` finds no document, living spec or source comment outside `openspec/changes/`, `docs/adr/` and the recorded fixtures that names a deleted test file.

## Existing Tool Considered

The validators that CI runs own the form of manifests and configuration: zizmor, actionlint, kube-linter, the kustomize build of the `k8s` row, Trivy config, `renovate-config-validator` and `uv lock --check`. No code is built.
