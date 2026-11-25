# Tasks

## 1. Test and SDLC rule update

Kind: other

Reads: `tests/invariants/test_agents_md.py`, `docs/SDLC.md`. Changes: `tests/invariants/test_agents_md.py`, `docs/SDLC.md`.

- [x] 1.1 Add an invariant test in `tests/invariants/test_agents_md.py` proving `docs/SDLC.md` uses priority-first PR ordering and permits explicit PR handoff or unclaimed pickup while protecting active session branches.
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md.py`
- [x] 1.2 Replace the strict FIFO queue and `Process only your own pull requests.` rules in `docs/SDLC.md` with priority-first triage and explicit handoff guidance.
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md.py`
- [x] 1.3 Run docs, OpenSpec, and fail-to-pass checks against `origin/main`.
  - Verification: `$ uv run devops ci docs && uv run devops ci openspec && uv run devops ci fail-to-pass --base origin/main`
