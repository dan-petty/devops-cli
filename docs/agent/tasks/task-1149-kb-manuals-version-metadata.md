# Task: Knowledge Base Manual Version Metadata, Matching Loader, and Review Grounding (#1149)

**Issue**: [#1149](https://github.com/dan-petty/devops-cli/issues/1149)
**Scope**: scope/review
**Feasibility**: Verified knowledge-base articles across `it_domains/tools/` (29), `it_domains/topics/` (11), and `devops_cli/libraries/` (23) against official upstream versions in `tools.lock` and Python 3.14 / v1.31.0 baselines. Front-matter parser parses YAML headers without modifying legacy markdown body structures. The matching loader inspects tools lock, CycloneDX package inventories, language floor, and Kubernetes version offline. Filtered references are budgeted alongside official rule docs with rule docs ranked first, and mismatched or undated manuals are reported under reference drift in `review.md`. All tests execute deterministically offline without network access or live models.

## Description

- [x] All 63 target manuals across `it_domains/tools/` (29), `it_domains/topics/` (11), and `devops_cli/libraries/` (23) carry structured YAML front-matter declaring `applies_to`, `sources`, `reviewed: "2026-10-15"`, and topic tags.
- [x] Knowledge-base loader `load_matched_kb_manuals` parses front-matter and evaluates `applies_to` constraints against `tools.lock`, locked packages, CycloneDX SBOM inventory, language floor (`python>=3.14`), and cluster `kubernetes_version`.
- [x] Matched manuals are assigned canonical reference keys of format `kb:<path>@<sha>` and indexed by producing tool, rule family, and topic tags.
- [x] Review group analysis jobs receive matched manuals corresponding to the group's producing tool and rule family via `filter_kb_manuals_for_group`.
- [x] Official rule docs rank first in reference budgeting before matched knowledge-base manuals.
- [x] Mismatched, corrupted, or undated manuals are excluded from group analysis prompts and recorded as `DriftManual` entries under `### Reference coverage: drift` in `review.md`.
- [x] Injected knowledge-base manuals are tracked and reported in `analysis.json` and rendered in review markdown.
- [x] All unit and integration tests run offline with zero network calls, no live model invocations, and finish in under 1s per test.
- Pending a person: verify on a live pull request review that injected manuals appear in model explanations and reference coverage matches the target repository environment.
