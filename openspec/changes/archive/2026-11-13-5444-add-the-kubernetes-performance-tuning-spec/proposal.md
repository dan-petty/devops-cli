# Proposal

## Why

Closes #5444. The owner asked on 2026-11-13 for three project specs: SRE service implementation, Kubernetes performance tuning, and agentic workflow implementation and tuning (#5443). This change is the Kubernetes part.

The first draft of this change was a spec with the measured state of one cluster: a node table, 22 rows measured with a date, the kubelet settings of each node, 22 queries and a gap table. Later on 2026-11-13 the owner gave three directions ([comment on #5444](https://github.com/dan-petty/devops-cli/issues/5444#issuecomment-6862800864)): split the details of one environment from the guidelines for each managed project, let programs give the metrics, and let no agent update each measured value by hand. The owner also decided that the gaps live in GitHub tracker issues, not in tables in git, and that live values and dated snapshots stay out of git. These directions replace the measured baseline of the issue.

## What Changes

- Move the spec to `docs/guidelines/kubernetes.md`, the Kubernetes guideline. It keeps only the parts that apply with no change to each managed project: the scope, the principles, 10 targets, the tuning loop, the formula to tune down from measured peaks, the A/B method, the rules of each area and 8 rules for agents and jobs. Each target names the kubernetes-mixin alert, the KRR report, the kube-linter check or the metric that measures it.
- Add a probe rule (readiness, liveness and startup probes, kube-linter `no-readiness-probe` and `no-liveness-probe`), and a batch Job rule: batch work runs as a Job that an event or a schedule starts, no service waits for it, and a Job that runs again on the same event gives the same result.
- Remove the node table, the measured state, the kubelet settings of each node, the queries and each measured sentence. The project review report, the dashboards and the commands give these values.
- Add the section "Capacity targets" to `k8s/README.md` with the decisions of this cluster: the pod start and runner start targets, the runner placement, the profiler decision and the infra repo that holds the node settings. It links gap tracker #5542 and holds no gap row.
- Add the line of this guideline to `docs/guidelines/index.md`, and name the guideline in the Guidelines line of `docs/index.md`. PR #5567 added the index, the "Guidelines" tab of `.nav.yml` and the guideline test first, with the same bytes as this change, so this change keeps their `main` versions. AGENTS.md does not change here: #5536 adds the route to the index.
- Remove `tests/docs/test_k8s_performance_spec.py` of the first draft, which requires a dated measured row. `tests/invariants/test_guidelines.py` checks the guideline: a guideline names no issue number, date, environment tree path, node, dating word (`today`, `currently`) or state row id (`S<n>`, `Q<n>`), and the index lists each guideline. This change wrote the test, and PR #5567 merged the same file first.
- Add the terms "Managed project" and "Guideline" to `CONTEXT.md`.
- Point the links of `docs/CLUSTER.md`, `k8s/README.md` and `docs/guidelines/sre.md` at the guideline. PR #5567 moved `docs/SRE.md` to `docs/guidelines/sre.md`.
- Carry no spec delta: the change moves documents and adds a test of documents. No command, option, message or manifest changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `docs/guidelines/kubernetes.md` (moved from `docs/K8S_PERFORMANCE.md`), `docs/guidelines/index.md` (one line), `docs/index.md`, `docs/CLUSTER.md`, `docs/guidelines/sre.md`, `k8s/README.md`, `CONTEXT.md`.
- Tests: none on `main`. `tests/invariants/test_guidelines.py` of PR #5567 checks the guideline.
- Gaps: tracker #5542 holds the gaps of the first draft as sub-issues and reference lines.

## Feasibility

- `uv run pytest tests/invariants/test_guidelines.py` failed on the text of the first draft (issue numbers, dates, node placeholders, state row ids), and passes on the guideline.
- The kubernetes-mixin source (`alerts/resource_alerts.libsonnet`) shows that `KubeMemoryOvercommit` and `KubeCPUOvercommit` check the loss of the largest node only for a cluster with 3 or more control-plane nodes, and that `CPUThrottlingHigh` uses `cpuThrottlingPercent` (25).
- The kube-linter check list (`docs/generated/checks.md`) has `unset-cpu-requirements`, `unset-memory-requirements`, `no-readiness-probe` and `no-liveness-probe`.
- The other targets, settings and defaults come from the Kubernetes pages on node-pressure eviction, reserved compute resources, PID limits, graceful node shutdown, probes, Jobs and the kubelet configuration.

## Existing Tool Considered

The guideline is a document, not code. Its targets use open tools: kubernetes-mixin (#4993), node-mixin, kube-state-metrics, KRR (#4992) and kube-linter (#5084). The guideline test uses `markdown-it-py`, which the tests already use. The change deletes `tests/docs/test_k8s_performance_spec.py`. Cost of the guideline test: about 120 lines, about 60,000 tokens and 1 hour.
