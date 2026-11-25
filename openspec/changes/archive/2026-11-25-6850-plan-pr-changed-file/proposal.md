# Proposal: #6850

## Why
`docs/SDLC.md` line 71 states that a plan pull request needs "a file added to `openspec/changes/<issue>-<slug>/`". However, `devops pr check-readiness` (`_PLAN_FILE_STATUSES` in `src/devops_cli/roadmap/grounding.py`) also accepts modified, renamed, copied, or changed files so corrections of merged plans pass. The documentation wording makes valid plan corrections look disallowed. Closes #6850.

## What Changes
- Update `docs/SDLC.md` line 71 from `a file added to \`openspec/changes/<issue>-<slug>/\`` to `a file added or changed in \`openspec/changes/<issue>-<slug>/\``.
- Add `test_sdlc_plan_pull_request_allows_a_changed_file` in `tests/invariants/test_change_folders.py` to assert the updated wording and reject the stale phrase.
- Set `skip_specs: true` because this change updates hand-written workflow documentation (`docs/SDLC.md`) with no behavioral change to CLI commands or `openspec/specs/`.

## Capabilities
None. Documentation clarification aligning `docs/SDLC.md` with existing `devops pr check-readiness` behavior.

## Impact
- `docs/SDLC.md`
- `tests/invariants/test_change_folders.py`

## Feasibility
Confirmed against `origin/main` (`feb4e969a`): `docs/SDLC.md:71` reads `a file added to \`openspec/changes/<issue>-<slug>/\``, while `src/devops_cli/roadmap/grounding.py:341-343` defines `_PLAN_FILE_STATUSES = frozenset({"added", "modified", "renamed", "copied", "changed"})`.

## Existing Tool Considered
No external tool updates a hand-written sentence in `docs/SDLC.md`; this edits the line directly and adds one invariant assertion (~1k tokens total).
