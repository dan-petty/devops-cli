# Proposal: #7092

## Why

In `#7092`, two legacy rules in `docs/SDLC.md` (`Phase 6`) block legitimate agent and contributor work:

1. `Sequential Pull Request Processing Queue (Strict Oldest-to-Newest / FIFO Execution)` requires processing open pull requests strictly from oldest to newest, which stalls `main`/release unblockers, requested pull requests, and `priority/p0-critical`/`priority/p1-high` fixes behind unrelated older or parked drafts and contradicts `Required Checks Gate the Merge`.
2. `Process only your own pull requests.` prevents fixing or adopting a stalled bot or cross-session pull request when requested or unclaimed, conflicting with `Branch Push Policy` ("any other branch that no other session works on").

Closes #7092.

## What Changes

- Update `docs/SDLC.md` (`Phase 6`) to prioritize broken `main`/release checks, explicitly assigned pull requests, and high-priority fixes ahead of equal-priority oldest-first triage, and to permit working assigned, handed-off, or unclaimed pull requests while protecting active session branches.
- Add an invariant test in `tests/invariants/test_agents_md.py` enforcing both updated rules in `docs/SDLC.md`.
- No product CLI behavior changes; this change updates documentation and tests only (`skip_specs: true`).

## Capabilities

None (`docs` and `tests` only).

## Impact

- Agents can triage urgent, assigned, or handed-off pull requests without head-of-line blocking from older parked drafts, while active session branches remain protected from uninvited edits.
- Fits in one pull request.

## Feasibility

Confirmed against `origin/main:docs/SDLC.md` lines 326, 331, and 352-355 and `tests/invariants/test_agents_md.py`. `docs/SDLC.md` currently enforces strict chronological FIFO and `Process only your own pull requests.`, with no invariant test asserting either legacy rule.

## Existing Tool Considered

Uses the existing markdown standards in `docs/SDLC.md` and the invariant suite in `tests/invariants/test_agents_md.py`; no new tool is built or needed, and no source code is added.
