# Task 554: Evaluation Run Store: Every Benchmark and Evaluation Saved and Shared

**Issue**: [#554](https://github.com/dan-petty/devops-cli/issues/554)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

Benchmarks and evaluations are meant to be repeated over the life of the tool, but only some keep results, each in its own shape: review profiles and benchmarks, corpora and sample validations under the data directory. `corpus score`, `ai gateway tune`, `ai prompt-eval` and `ai benchmark` (without `--output`) keep nothing. Nothing is shared between workstations: Valkey is unreachable from them and keeps its data on an `emptyDir`.

#### Key Deliverables:
- Context & Rationale*: Benchmarks and evaluations are meant to be repeated over the life of the tool, but only some keep results, each in its own shape: review profiles and benchmarks, corpora and sample validations under the data directory. `corpus score`, `ai gateway tune`, `ai prompt-eval` and `ai benchmark` (without `--output`) keep nothing. Nothing is shared between workstations: Valkey is unreachable from them and keeps its data on an `emptyDir`.
- Deliverable*: One run record per mechanism under the data directory. It holds the mechanism, run id, time, devops-cli version and commit, a fingerprint of the setup (models, backends and weights, page size, personas), the subject (corpus digest, sample commits, target) and the results. Every mechanism writes one: corpus scores with each injection's candidates, gateway tune, AI benchmarks and prompt evaluation included. Records are mirrored to a reachable, persistent Valkey as a shared index. The data directory stays the source of truth, a command rebuilds the index, and everything works without Valkey, saying so.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
