# Design

## Context

The synthetic corpus generator injects artificial defects into code and documentation. The review pipeline evaluates tools against these defects. See `proposal.md` for motivation.

## Goals / Non-Goals

**Goals:**
- Remove the untestable `contradict-documented-default` template from `src/devops_cli/ai/review/defects.py`.
- Preserve documentation defect coverage in tests using fenced code block mutations.
- Ensure `select_templates` rejects the removed template name.

**Non-Goals:**
- Add new rule-pack rules for detecting documentation default contradictions.
- Modify existing task files for completed issues #504 and #505.

## Decisions

### Decision 1: Remove the template rather than constrain its injection sites
- **Choice**: Delete `contradict-documented-default` completely.
- **Rationale**: ADR 0005 states that defects that no tool or rule can express are out of scope. Persona reviews are deleted in #1151, leaving no detector for prose defects.
- **Alternatives Considered**:
  - Restrict injection to files containing the default definition (for example, Terraform variable descriptions). Rejected: detecting such defects requires a new rule-pack rule, which exceeds the scope of this measurement task.

### Decision 2: Do not introduce accepted-loss markers in the corpus scorer
- **Choice**: Keep `CorpusScore` unchanged.
- **Rationale**: `AcceptedLoss` belongs in label files (`src/devops_cli/review/score.py`).
- **Alternatives Considered**:
  - Add an accepted-loss marker to `CorpusScore` in `src/devops_cli/ai/review/defects.py`. Rejected: this represents compensating code.

### Decision 3: Use widen-file-mode for docs coverage in the corpus integration test
- **Choice**: In `test_a_corpus_of_infrastructure_and_docs_records_each_injection`, change `README.md` to contain a fenced `chmod 600` block and inject `widen-file-mode`.
- **Rationale**: Fenced code blocks test documentation defect injection without prose mutation.
- **Alternatives Considered**:
  - Use `disable-tls-verify` in `README.md`. Rejected: `disable-tls-verify` can also match `RUN_CHAIN` in the `Dockerfile`, altering the seeded template selection.

## Risks / Trade-offs

[Risk] Documentation files receive fewer synthetic mutations in benchmarks.
→ [Mitigation] Documentation files continue to receive code block mutations such as `widen-file-mode`, `disable-tls-verify`, and `pipe-to-shell`.
