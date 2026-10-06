# Task 408: Cluster Deployment Health Diagnosis (`devops k8s doctor`)

**Issue**: [#408](https://github.com/dan-petty/devops-cli/issues/408)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: type/feature, scope/k8s

---

## 1. Description & Objectives

A review of live cluster logs surfaced failures that are individually obvious and collectively invisible, because nothing correlates them. A node left `NotReady,SchedulingDisabled` had `metrics-server` retrying it every 12 seconds — six restarts and a log filled entirely with one unreachable host — while a `PersistentVolume` delete had been timing out for three days behind a helper pod stuck `Terminating`. Each is a one-line symptom; none is reported anywhere an operator looks.

This deliverable implements `devops k8s doctor` and its corresponding FastMCP tool `k8s_doctor`: a cluster health diagnosis command that correlates node readiness, pod restart counts, `Warning` events, and container logs into a deterministically ranked list of deployment problems, identifying root causes and recommending actionable remediations.

Key capabilities delivered:
- Fixed evaluation rule table with root-cause attribution: cluster faults absorb workload symptoms (e.g. crashlooping pods on an unready or cordoned node are absorbed into the node finding).
- Cluster-wide PersistentVolume reclaim diagnosis (`VolumeFailedDelete` events) and stuck terminating pod detection.
- FastMCP tool `k8s_doctor` registered with docstring documenting status code conventions (`2` indicates findings follow as JSON, `1` indicates unreachable cluster).
- Pure function collection and diagnosis engine in `src/devops_cli/k8s/doctor.py` making Kubernetes API calls only (no Prometheus or LogQL dependencies).
- Bounded container log tailing for flagged pods with secret sanitization via `mask_secrets`.
- Output formatting support for `table`, `json`, and `yaml` with exit codes `0` (clean), `2` (findings present), and `1` (error).
- Read-only `--dry-run` execution previewing ordered API requests without making requests.

---

## 2. Acceptance Criteria

- [x] `uv run devops k8s doctor --help` lists `--namespace`, `--context`, `--tail`, `--format`, and `--dry-run`; tested via CliRunner in `tests/test_k8s_doctor.py::test_doctor_is_registered_with_its_options`.
- [x] Node unreadiness absorbs crashlooping pods into `affected` resources rather than reporting duplicate workload findings; tested in `tests/test_k8s_doctor.py::test_doctor_attributes_crashloop_on_an_unready_node_to_the_node`.
- [x] PersistentVolume `VolumeFailedDelete` warning event and stuck terminating helper pod are detected and ranked; tested in `tests/test_k8s_doctor.py::test_doctor_reports_a_stuck_volume_reclaim`.
- [x] Parametrized fixture test suite validates all diagnostic rules (`node-cordoned`, `pod-stuck-terminating`, `pod-crashloop` with `OOMKilled`, `pod-image-pull`, `pod-unschedulable`, `pod-not-ready`, `warning-events`, `log-errors`); tested in `tests/test_k8s_doctor.py::test_doctor_rules`.
- [x] Deterministic finding ranking pins cluster findings before workload findings, critical before warning; tested in `tests/test_k8s_doctor.py::test_doctor_ranks_cluster_findings_first`.
- [x] Logs are read only for flagged pods with requested tail lines; tested in `tests/test_k8s_doctor.py::test_doctor_reads_logs_only_for_flagged_pods`.
- [x] Every API call carries client-side timeout `DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS`; tested in `tests/test_k8s_doctor.py::test_doctor_calls_carry_a_timeout`.
- [x] Doctor uses the Kubernetes API only and imports nothing from Prometheus or LogQL; tested in `tests/test_k8s_doctor.py::test_doctor_uses_the_kubernetes_api_only`.
- [x] `--namespace` narrows pod and event listing to the target namespace; tested in `tests/test_k8s_doctor.py::test_doctor_namespace_narrows_the_calls`.
- [x] `--format json` and `--format yaml` serialize the report cleanly; tested in `tests/test_k8s_doctor.py::test_doctor_json_output_round_trips`.
- [x] Exit codes are `0` for clean, `2` for findings, and `1` for error/unreachable with secret masking; tested in `tests/test_k8s_doctor.py::test_doctor_exit_codes`.
- [x] `--dry-run` loads no kubeconfig, makes no API calls, and outputs planned requests; tested in `tests/test_k8s_doctor.py::test_doctor_dry_run_makes_no_request`.
- [x] FastMCP tool `k8s_doctor` registered and documented; verified via MCP contracts and `devops docs check`.
- [x] Changelog fragment `changelog.d/408.md` authored.
- [x] All tests run offline in under 1 s per test and pass in `uv run devops ci`.
- Pending a person: `uv run devops k8s doctor --context homelab-k3s` on the homelab, then `uv run devops k8s doctor --context homelab-k3s --format json | head -40`, and confirm the output agrees with `kubectl --context homelab-k3s get nodes` and `kubectl --context homelab-k3s get events -A --field-selector type=Warning`, and that the shell's `$?` is `2` when the table shows findings and `0` when it does not.

---

## 3. Deliverables

- [x] `src/devops_cli/config/constants.py`: Added `CONST_K8S_DOCTOR_*`, `CONST_K8S_KIND_PERSISTENT_VOLUME`, `CONST_K8S_REASON_*`.
- [x] `src/devops_cli/config/defaults.py`: Added `DEFAULT_K8S_DOCTOR_*` thresholds and tail lines.
- [x] `src/devops_cli/models/k8s.py`: Added `NodeInfo`, `ClusterEventInfo`, `Finding`, and `DoctorReport` domain models.
- [x] `src/devops_cli/k8s/doctor.py`: Implemented `Snapshot`, `plan_doctor_requests`, `collect`, `diagnose`, and `get_k8s_client`.
- [x] `src/devops_cli/commands/k8s/diagnostics.py`: Registered `doctor_cmd` with formatting, dry-run, and exit code handling.
- [x] `src/devops_cli/commands/k8s/__init__.py`: Registered `doctor` command in k8s subcommand router.
- [x] `src/devops_cli/ai/mcp/server.py`: Added `k8s_doctor` tool with documented exit code 2 convention.
- [x] `docs/CLI_REFERENCE.md` & `docs/MCP_TOOLS.md`: Regenerated via `devops docs generate`.
- [x] `tests/test_k8s_doctor.py`: Added comprehensive offline test suite covering all 12 criteria.
- [x] `tests/test_fastmcp_contracts.py` & `tests/test_mcp.py`: Updated MCP tool registration contracts and test assertions.
- [x] `changelog.d/408.md`: Created changelog fragment.
