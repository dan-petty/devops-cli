# Task: Refine writes its section's end marker, so a re-refined item keeps one design section (#1470)

**Issue**: [#1470](https://github.com/dan-petty/devops-cli/issues/1470)
**Status**: Done
**Milestone**: v0.2.33
**Priority**: priority/p2-medium
**Scope**: type/bug, scope/roadmap
**Feasibility**: Reproduced on release/v0.2.33 (4635fdd): with the unfixed `render_proposal_section`, the refine-twice test below left two `## Proposed design` sections, and the round-trip test found no section. Both markers are HTML comments, which `sanitize_text`'s tag pattern (`<[a-zA-Z/]`) leaves alone, so only its end-marker replacement removed the section's own end marker.

## Description

`render_proposal_section` (`src/devops_cli/roadmap/refine.py`) appended the end marker to the section and then passed the whole section through `sanitize_text`, whose first step replaces the end marker with `[end-marker]`. Every section refine wrote ended in `[end-marker]`, `extract_section_and_outside` found no section, and the next refine of the item appended a second one.

The renderer now sanitizes the section's text first and then wraps it in the start and end markers. An end marker in the model's text is still neutralised to `[end-marker]`; the section's own is never touched. No other change.

Out of scope (the owner made it optional): the path-resolution add-on from the issue's 2026-10-09 comment (`_is_valid_source` accepting `Caddyfile:54` for a single tracked `caddy/Caddyfile`) needs a tracked-file lookup and a resolved path carried back into the proposal's sources, more than a few lines.

An item that already holds a section from before this fix (ending in `[end-marker]`; none in this repository holds one, and one item in a managed repository does) gets one correctly marked section on its next refine; refine then skips it with "the section's hash differs from the one refine last recorded" until a person deletes the old section.

## Acceptance Criteria

- [x] Round trip: `extract_section_and_outside(body + render_proposal_section(...))` returns the original body and the section's text, with the model's text holding an end marker (`test_a_rendered_section_keeps_its_end_marker_when_the_model_writes_one`).
- [x] Refining an item twice, with a body edit between, leaves exactly one design section, the second run's, and keeps the edit (`test_refining_twice_with_a_body_edit_between_leaves_only_the_second_section`).
- [x] Model text that contains the end marker is still neutralised (the round-trip test above; `test_sanitize_text_markdown` keeps passing).
- [x] `changelog.d/1470.md` under `### Fixed`.

## Deliverables

- [x] `src/devops_cli/roadmap/refine.py`: `render_proposal_section` adds the markers after `sanitize_text`.
- [x] `tests/test_roadmap_refine.py`: the round-trip and refine-twice tests.
- [x] `changelog.d/1470.md`.
