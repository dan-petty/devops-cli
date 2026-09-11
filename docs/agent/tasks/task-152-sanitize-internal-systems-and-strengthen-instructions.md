# Task 152: Sanitize Internal Homelab Hostnames, IPs, and Mount Paths & Strengthen Agent Instructions

**Issue**: [#152](https://github.com/dan-petty/devops-cli/issues/152)
**PR**: [#151](https://github.com/dan-petty/devops-cli/pull/151)
**Status**: In Review
**Milestone**: `v0.2.16`
**Priority**: `priority/p1-high`
**Scope**: `scope/agent`

---

## 1. Description & Objectives

Sanitize all references to internal systems, homelab configurations, physical node hostnames, private LAN hostnames, RFC 1918 IPs, and hardware mount paths that slipped into task tracking and documents. Update agent instructions and scaffolding tools to cover the issue comprehensively and prevent future recurrence.

---

## 2. Planned Changes

1. **Configuration & Manifest Sanitization**:
   - `config.yaml`: Replace internal LAN hostnames (`hog.lan`, `condor.lan`, `hawk.lan`, `workhorse.lan`) and non-standard endpoints with generic localhost defaults (`http://localhost:11434`, `http://localhost:6333`).
   - `k8s/squid/deployment.yaml`: Replaced `condor` node affinity with generic `<storage-node>` and container image with public GHCR reference.
   - `tests/test_k8s_squid.py`: Aligned node affinity assertions with generic `storage-node`.
2. **Task Tracking & Documentation Sanitization**:
   - `docs/agent/tasks/task-141-squid-proxy-cluster-enablement.md`: Generalized cluster references and removed NodePort references.
   - `docs/agent/tasks/task-135-k8s-pod-restarts-resource-limits.md`: Sanitized physical node names, drive paths (`/mnt/nvme*`, `/dev/sd*`), and container IDs to generic placeholders.
   - `docs/agent/tasks/task-142-llm-gateway-distributed-router.md`: Replaced specific hardware references with generalized multi-GPU worker nodes.
   - `docs/ROADMAP.md`: Removed specific hardware node names and replaced with architectural roles.
   - `docs/squid-failover-and-observability.md`: Removed local storage capacity and node naming specifics.
   - `docs/agent/archive/historical-phases-1-to-50.md`: Scrubbed references to specific private registry configurations.
3. **Agent Instructions & Instruction Generator Updates**:
   - `AGENTS.md`: Update Section 1 ("Zero-Trust Security & Egress Safety") to explicitly mandate Zero Information Leakage and Comprehensive Environment Sanitization, strictly prohibiting recording internal hostnames, RFC 1918 IPs, private registries, NodePort endpoints, physical storage paths, or homelab topology details, and mandating abstract roles and RFC 5737 placeholders.
   - `src/devops_cli/ai/instruction_generator.py`: Update `generate_agents_md()` to embed the comprehensive environment sanitization policy in all generated instruction files.
   - `tests/test_instruction_generator.py`: Add unit tests asserting the comprehensive environment sanitization policy is scaffolded.
4. **Verification**:
   - Run `devops docs generate --sync-readme`.
   - Run full CI quality gate (`uv run devops ci`).
