# Design

`CONST_HARDENING_SURFACES` lists the declared surfaces where defect pull requests must record hardening guardrails or lessons.

The constant replaces `AGENTS.md` with the four owning documents:
- `docs/TESTING.md`
- `ARCHITECTURE.md`
- `SECURITY.md`
- `CONTRIBUTING.md`

The checks and knowledge base surfaces remain unchanged:
- `src/devops_cli/ai/tasks/*.md`
- `src/devops_cli/ai/knowledge_base/`
- `.devops/review.toml`
- `src/devops_cli/review/rules/`

`match_hardening_surface` in `src/devops_cli/github/defect_classifier.py` matches the normalized file path against the declared surfaces. Exact string equality is used for each owning document.

The post-merge audit workflow `.github/workflows/defect-pr-hardening-audit.yml` lists the identical surfaces in its intake finding template.

## Rejected Alternatives

- **Keep AGENTS.md in addition to owning documents**: Rejected. `AGENTS.md` is a router document with a strict character budget. Storing defect lessons in `AGENTS.md` violates the architectural invariants established in #1961.
- **Match all markdown files**: Rejected. Hardening surfaces must remain intentional and declared to prevent arbitrary documentation edits from satisfying the defect hardening requirement.

## Test

- Unit tests in `tests/test_defect_classifier.py` test `match_hardening_surface` against all declared surfaces, verify `AGENTS.md` returns `None`, and assert consistency with `.github/workflows/defect-pr-hardening-audit.yml`.
- `tests/test_pr_hardening_report.py` validates that defect pull requests modifying the owning documents are classified as hardened, while additions to `AGENTS.md` do not satisfy hardening.
- Fail-to-pass test suite demonstrates failure on unpatched base and success on patched code.
