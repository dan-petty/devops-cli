# Proposal: #4823

## Why

PR #4800 merged with two review findings that it did not fix. The Nested Time Limits bullet of `ARCHITECTURE.md` is out of the STE limits of `src/devops_cli/ai/tasks/style_ste100.md`: it has 8 sentences, one sentence of 42 words, and procedure sentences of more than 20 words with two instructions. The board audit line of `docs/ROUTINE_TASKS.md` repeats the rule "No roadmap job reads the board", but `docs/SDLC.md` owns that rule, and each rule must be in one document only. Closes #4823.

## What Changes

- `ARCHITECTURE.md`, Nested Time Limits: keep a short lead of two sentences. Put each instruction in its own sub-bullet. Put the known break (#4678) and the idle cut of the tunnel in their own sub-bullets. Keep each fact of the old text.
- `docs/ROUTINE_TASKS.md`, board audit line: remove the copy of the rule and keep only the link to `docs/SDLC.md`, Phase 1, Status Lives on GitHub.
- The change edits documents only and alters no behavior that a consumer observes, so it has no spec delta.
- The change fits one pull request.

## Capabilities

None. The change edits two documents.

## Impact

- `ARCHITECTURE.md` and `docs/ROUTINE_TASKS.md`. No code, setting, test or dependency changes.
- The archived change folder of #4788 stays as it is. It records what #4800 delivered.

## Feasibility

Each fact was checked on `origin/main` at d83c7d9a:

- `git show origin/main:ARCHITECTURE.md | sed -n '155p'` shows the Nested Time Limits bullet as one paragraph of 8 sentences. One sentence has 42 words.
- `src/devops_cli/ai/tasks/style_ste100.md` sets one instruction for each sentence, at most 20 words for a procedure sentence, at most 25 words for a description sentence and at most 6 sentences for a paragraph.
- `git grep -n "No roadmap job reads the board" -- docs/` found `docs/ROUTINE_TASKS.md:270`. `docs/SDLC.md`, Phase 1, Status Lives on GitHub, says that no roadmap job reads or writes the project board.

## Existing Tool Considered

None applies. The change corrects text in two documents and builds no code. It deletes no internal code.
