# Task 278: Living Mental Model Synthesizer & Causal Graph Distiller (`devops ai research model`)

**Issue**: [#278](https://github.com/dan-petty/devops-cli/issues/278)
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`
**Feasibility**: Verified against `devops_cli.ai.research` module, YAML serialization, and Typer CLI runtime.

---

## 1. Description & Objectives

Progressively compacts sprawling research observations into a concise, living mental model (`.data/research/mental_model_<topic>.yaml`).

#### Key Deliverables:
- [x] Structured mental model schema: `StateTransition`, `CausalGraph` (DAG with `CausalNode` and `CausalEdge`), and `InvariantRule`.
- [x] Persistent YAML storage keyed by topic slug at `.data/research/mental_model_<topic>.yaml`.
- [x] Progressive revision synthesis engine `MentalModelSynthesizer` that preserves prior model structure across revisions.
- [x] Command `devops ai research model <topic>` supporting `--observations`, `--file`, `--show`, and YAML, JSON, Markdown, and table formatting.
- [x] Unit and integration test coverage with structural tuple equality assertions in `tests/test_ai_research_mental_model.py`.
- [x] Complexity $M \le 10$ and nesting depth $\le 5$ enforced.
- [x] 100% passing across Gated CI validation suite (`uv run devops ci`).
