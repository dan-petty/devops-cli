# Design

## Decisions
- Replace `"a file added to \`openspec/changes/<issue>-<slug>/\`"` with `"a file added or changed in \`openspec/changes/<issue>-<slug>/\`"` at `docs/SDLC.md:71` so documentation matches `_PLAN_FILE_STATUSES` in `src/devops_cli/roadmap/grounding.py:341-343`.
- Add `test_sdlc_plan_pull_request_allows_a_changed_file` to `tests/invariants/test_change_folders.py` to keep the wording accurate over future edits.

## Rejected alternatives
- **List every git status (`added, modified, renamed, copied, or changed`)**: unnecessarily verbose when `"added or changed"` matches the issue request and remains accurate.
- **Documentation edit without a test**: provides no automated regression check against reintroducing `"a file added to"`.
