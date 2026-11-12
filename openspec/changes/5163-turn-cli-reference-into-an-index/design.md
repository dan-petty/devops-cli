# Design

## Decisions
- **One page holds the index and the matrix.** The issue moves the README matrix into the generated reference. The index table comes first, so a reader finds the page of a group at once, and the matrix follows it. The page has 56,284 characters, below the 100,000 characters that a web fetch reads.
- **Links are relative to `docs/`.** A row links `commands/<group>.md`, so the link works on github.com and on the docs site, and the strict build checks it.
- **The page of a group holds the description of the group.** The old CLI reference was the only page that showed it for seven groups, so the description moves to the group page and no text is lost.
- **No README option and no shim.** The alpha rule deletes `devops docs sync-readme`, `--sync-readme/--no-sync-readme` and `--check-readme/--no-check-readme`. `write_all_docs` and `check_docs` lose their README parameters, and the generator returns no `README.md`.
- **Records keep the old name.** The docs inventory classes `openspec/changes/`, `tests/fixtures/roadmap_eval/`, `docs/adr/` and `docs/agent/archive/` as records. A builder ticks the task lines of an active change, so an edit of those lines here would conflict with that branch. ADR 0025 decided the README matrix, so it gets a note at its top, as its own section on drift asks. The one exception is the good plan of the stage eval case `good-3264`: the `paths` gate refuses a cited command that the live command tree does not have, and a good plan must pass every gate, so its documentation text names `uv run devops docs generate`.
- **#4781 keeps its lines.** This change edits only the argv of `_generate_docs` in `implement_run.py`. #4781 changes `_commit_if_changed`, so the two changes touch different lines.

## Rejected alternatives
- **Keep the README matrix and add the index.** The owner approved the move on 2026-11-12, and two copies of the matrix need two sync paths.
- **A link to the anchor of each group on one long page.** That keeps the 419,891 characters that a page fetch cannot read.
- **A generalized marker-block function now.** #4889 plans it for the README matrix and the `docs/index.md` list. With no README block left, this change has no caller for it, so #4889 adds it with its first caller.
