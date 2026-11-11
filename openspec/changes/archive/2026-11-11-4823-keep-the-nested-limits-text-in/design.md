# Design

## Decisions

- The bullet keeps a lead of two sentences that gives the rule and its reason. Each nesting pair is a sub-bullet with one instruction, so each procedure sentence has one instruction and at most 20 words.
- The known break (#4678) and the idle cut of the tunnel are sub-bullets, because they are descriptions and not instructions.
- `docs/ROUTINE_TASKS.md` keeps only the link to `docs/SDLC.md`, because Phase 1, Status Lives on GitHub, owns the board rule.

## Rejected alternatives

- Move the Nested Time Limits text to a new document. Rejected: `ARCHITECTURE.md` owns the cross-cutting design rules, and a split of the bullet is sufficient to meet the STE limits.
- Edit the archived change folder of #4788 to match. Rejected: that folder records what #4800 delivered, and a pull request must not write the archived folder of another issue.
