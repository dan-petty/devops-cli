# Task 413: Model-in-the-Loop Prompt Benchmarking

**Issue**: [#413](https://github.com/dan-petty/devops-cli/issues/413)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

`devops ai prompt-eval` now measures the deterministic suppression layer against recorded verdicts, which is honest but covers only the checks that run before a model is asked. Nothing measures a prompt. The two hot-path prompts were compressed by 32% in v0.2.22 on the argument that no decision was lost, and that argument rests on a keyword coverage test rather than on any observed change in output. Every prompt edit since this project began has shipped the same way.

#### Key Deliverables:
- Context & Rationale*: `devops ai prompt-eval` now measures the deterministic suppression layer against recorded verdicts, which is honest but covers only the checks that run before a model is asked. Nothing measures a prompt. The two hot-path prompts were compressed by 32% in v0.2.22 on the argument that no decision was lost, and that argument rests on a keyword coverage test rather than on any observed change in output. Every prompt edit since this project began has shipped the same way.
- Deliverable*: Replay a fixed corpus of reviewed segments through a candidate prompt and the current one, with a pinned model and temperature, and report the difference in findings produced, findings later invalidated, and tokens spent. A prompt change becomes a measured trade rather than an assertion.
- Constraint*: The corpus has to carry ground truth that was not produced by the loop being measured. The feedback dataset's 1066 `VERIFIED` records were labelled by the same verifier under test, and two calibration sessions found roughly 40% and 85% of high-severity findings in those sessions to be false positives — so `VERIFIED` is not a label, it is a prior. The 122 human-verified records are the only trustworthy seed, and the corpus needs to grow from there.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
