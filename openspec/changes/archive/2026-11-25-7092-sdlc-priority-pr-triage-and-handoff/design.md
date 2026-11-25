# Design

## Decisions

- Replace strict chronological FIFO in `docs/SDLC.md` with priority-first pull request ordering (`main`/release blockers, explicitly assigned pull requests, and `p0`/`p1` fixes before lower-priority items, using oldest-first order among actionable pull requests within a priority tier).
- Replace `Process only your own pull requests.` in `docs/SDLC.md` with explicit handoff/assignment/unclaimed ownership while keeping protection against pushing onto another active session's branch (`Branch Push Policy`).
- Keep `Push When the Work Is Complete` in `docs/SDLC.md` unchanged because it reflects the standing owner push rule (`#4751`).

## Rejected alternatives

- **Keep strict oldest-to-newest FIFO with a carve-out note only in chat**: rejected because `docs/SDLC.md:352-354` is loaded as canonical repository guidance and already contradicts `docs/SDLC.md:331` ("fix it before other work" when a release check fails).
- **Remove `Push When the Work Is Complete` in the same change**: rejected because `git show 84df338ec` (`#4751`) shows the owner explicitly established that rule for workstation drafts, whereas `docs/SDLC.md:352-355` came from legacy setup (`v0.2.18`) and conflicts with `docs/SDLC.md:326` and `:331`.
