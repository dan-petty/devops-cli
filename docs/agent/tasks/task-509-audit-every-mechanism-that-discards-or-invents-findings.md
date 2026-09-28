# Task 509: Audit Every Mechanism That Discards or Invents Findings, With a Regression Harness

**Issue**: [#509](https://github.com/dan-petty/devops-cli/issues/509)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p0-critical`
**Scope**: `type/bug`, `scope/review`, `priority/p0-critical`

---

## 1. Description & Objectives

A finding passes through a series of mechanisms before it reaches the report:
- deterministic pre-verification checks;
- the hallucinations catalog and its learning loop;
- LLM verification;
- merging, reranking, suppression and redaction;
- the report's filters;
- before any of those, the persona prompts and page building.

Each can discard a real defect or keep a false one. The missing-symbol check invalidated real
"missing check" findings and taught them to the catalog (#500). On a synthetic corpus of 10 known
defects, the personas found 7 and 1 survived verification (#415).

### Key Deliverables Completed:

- [x] **Audit**: four read-only audits, one per layer, listed about 60 mechanisms that change a
  finding's fate, each with its trigger and a concrete misfire. The consequential claims were
  reproduced before any fix: scanner findings overwritten, one malformed field dropping a reply,
  distinct defects merged, redaction rewriting code, and the catalog block listing real defects.
  Dispositions:

  | Layer | Mechanisms | Where |
  | :--- | :--- | :--- |
  | Pre-verification | missing-symbol trigger on "missing" | #500 |
  | Pre-verification | syntax, health/stream, None, pathlib, auth-header, fixture-secret, masked-marker, monologue and compliment substring triggers; line past EOF; runtime floor from devops-cli | #513 |
  | Verdicts | string booleans, "none" criteria, contradiction, uncertainty hiding a finding, binding by shared line or missing title | #513 |
  | Catalog | learning from LLM verdicts and replays, builtin pollution and shadowing, no list or remove, syntax, symbol, header and CWE-400 ground truth, learned entries in prompts | #514 |
  | Between reply and report | scanner findings overwritten, whole-reply parse loss, distinct defects merged, titles blanked, persona-set status, redaction rewriting code, severity synonyms | #512 |
  | Prompts | verifier's devops-cli assumptions, persona house rules, absence bans, roadmap mandates, "drop the already-mitigated", mitigation treated as refutation | #515 |
  | Scope | PR reviews reading the local checkout, substring page mapping, code classified as documentation, lockfiles never scanned | #515 |
  | Scanners | a missing scanner reported as a clean scan | #516 (open) |
  | Pages | no line numbers; splits without overlap | #499 (open) |
  | Locations | paths containing `+`, `@`, `~` or `%` | #498 (open) |
  | UI | dashboard refresh racing panel mount | #519 (v0.2.24) |

- [x] **Regression harness** (`tests/test_review_regression_harness.py`, `tests/golden/review_findings.json`):
  - 23 real defects are driven through every layer that runs without a model:
    - parsing a persona reply carrying a malformed field;
    - resetting persona-written state;
    - consolidation;
    - deterministic pre-verification against files on disk, catalog included;
    - the report's filter.

    Each must be reported.
  - Two groups of distinct defects must stay distinct, and nine known false alarms must still be
    invalidated.
  - The real defects come from the synthetic corpus's injected defects and the audit's
    reproductions, never from the verifier under test.
  - Reintroducing three of the audit's defects fails the harness: the missing-symbol trigger
    (12 failures), a persona setting its own status (1) and filler words merging defects (1).
- [x] **A defect the harness found**: two #512 and #513 fixes interacted. Verification drops a
  miscounted line, and consolidation then merged a line-less "Hardcoded secret: `DB_PASSWORD`"
  into "Hardcoded secret: `AWS_KEY`" by title. Findings without lines to compare now stay apart
  when they name different code symbols.
- [x] **Learned catalog entries can be listed and removed** (#514).
- [x] **Automated Tests & Quality Gates**: the harness runs in CI with the rest of the suite; 100%
  passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on a Live Cluster

The #415 corpus of 10 injected defects, reviewed with all personas as the fixes landed:

| | Injections found | Injections still reported | Findings reported in total |
| :--- | ---: | ---: | ---: |
| Before (#415) | 7 | 1 | 1 |
| #500, #512, #513 merged | 9 | 6 | 34 |
| #515 part 2 | 8 | 6 | 41 |

Five of the six reported injections are genuine matches. In the last run the verifier invalidated
16 of 57 candidates, down from 39 invalidations it made before #515. It now states mitigations in
the report instead of invalidating, and some of them are wrong in plain view. That is the verifier
model's reasoning quality, measured per backend in #475.
