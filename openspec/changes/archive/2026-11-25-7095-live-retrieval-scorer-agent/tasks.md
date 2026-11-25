# Tasks

## 1. Remove non-release person restrictions and test invariants

Kind: other

Reads: `tests/invariants/test_agents_md.py`, `docs/TESTING.md`, `docs/ROADMAP_WORKFLOW.md`. Changes: `tests/invariants/test_agents_md.py`, `docs/TESTING.md`, `docs/ROADMAP_WORKFLOW.md`.

- [x] 1.1 Extend `_REMOVED_PERSON_STEP_PHRASES` in `tests/invariants/test_agents_md.py` with the three retired person-only phrases from `docs/TESTING.md` and `docs/ROADMAP_WORKFLOW.md`.
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md.py`
- [x] 1.2 Update `docs/TESTING.md` line 140 and `docs/ROADMAP_WORKFLOW.md` lines 283 and 352 to allow agent execution under ADR 0038 Decision 3 while keeping CI offline and owner gates intact.
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md.py tests/invariants/test_roadmap_workflow_doc.py`
- [x] 1.3 Run docs, OpenSpec, and fail-to-pass checks against `origin/main`.
  - Verification: `$ uv run devops ci docs && uv run devops ci openspec && uv run devops ci fail-to-pass --base origin/main`
