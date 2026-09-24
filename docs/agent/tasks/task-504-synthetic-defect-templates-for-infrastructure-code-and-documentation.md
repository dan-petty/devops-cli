# Task 504: Synthetic Defect Templates for Infrastructure Code and Documentation

**Issue**: [#504](https://github.com/dan-petty/devops-cli/issues/504)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/review`, `priority/p2-medium`

---

## 1. Description & Objectives

Infrastructure code and documentation get reviewed too, but the generator covers only a few YAML and Dockerfile patterns.

#### Key Deliverables:
- Terraform (encryption off, `0.0.0.0/0` ingress, public access), Dockerfiles (running as root, remote `ADD`), shell (dropped `set -euo pipefail`, unquoted expansions, `curl -k`, piping a download to a shell), Kubernetes (`hostNetwork`, `hostPath`, missing limits) and technical documentation (an insecure example command, a documented default that contradicts the code).
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
