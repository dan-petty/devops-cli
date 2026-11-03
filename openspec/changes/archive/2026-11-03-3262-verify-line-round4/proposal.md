# Proposal

## Why

Issue #3262, third follow-up. The review of the second follow-up found one major fault and five smaller ones.

1. A split reply skipped `form_problems`. `_settle` checked the paths and the criteria of the new groups only, so a split group with `` `uv run devops ci test tests/x.py` and `git push origin HEAD` `` as `verify` gave two commands to the step.
2. U+FEFF is white space for the JavaScript `\s` of `openspec`, and not for Python. A purpose of U+FEFF, `##`, U+FEFF and `REMOVED Requirements` passed the check for a mark at the start of a line.
3. `section_text` read a heading of every level, so a nested `- ## Why` leaked into the text of the delivery pull request, and an HTML block at the start of a text hid the rest of the file.
4. The stage prompt did not tell the model the rule of the schema.
5. Three marks had no test.

## What Changes

- `_settle` calls `form_problems` on the groups of a split reply. Every other path that settles groups already goes through `check_proposal` (a revised plan calls `_settle`).
- `_one_line` and `_join_lines` turn U+FEFF into a space. It is the one character of the JavaScript `\s` class that Python does not take as white space.
- `_BLOCK_START` refuses an HTML tag (`<` and a letter, `/`, `!` or `?`) at the start of a text.
- `section_text` takes a heading at the top level only.
- The stage prompt tells the model that `why`, `existing_tool`, `purpose` and the `text` of a requirement are on one line and start with a word.
- Tests: the split reply, U+FEFF, HTML tags, `~~~`, `___`, a bare `##`, the prompt, `section_text`, and a ratchet that fails when a text field of a `Stage*` model is neither folded nor named with its other check.
- Spec delta for `roadmap-stage`: one ADDED and one MODIFIED requirement.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A split reply is checked for the form of its commands, A text of the proposal, the design and the spec delta stays on one line (MODIFIED)

## Impact

- Code: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- Tests: `tests/roadmap/test_roadmap_stage_text_lines.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_kind.py`.

## Dependencies

None open.

## Feasibility

Checked on `origin/main` 987280ea, on 2026-11-03, in a plain clone.

1. `form_problems` is called by `check_proposal` (`stage_change.py`), and `_settle` calls `check_proposal` for a reply and for a revised plan. The split branch of `_settle` calls `path_problems` and `criterion_problems` only. The test of a split group with a wrong `verify` fails on the base: the group is accepted.
2. The JavaScript class `\s` is `[\t\n\v\f\r    -     　﻿]`. Python's `str.split` takes all of these except U+FEFF, and takes `\x1c` to `\x1f` and `\x85` besides, which JavaScript does not need. So U+FEFF is the only gap. The tests with U+FEFF fail on the base.
3. `section_text` is used by the pull request description and by the rules of the step. The test with a nested `- ## Why` fails on the base.
4. All the new tests that pin the faults above fail on the base (12 tests).

Not verified: a live stage run with a model.

## Existing Tool Considered

None covers it: it is the schema and the job of this project. Cost to build: about 25,000 tokens and about 45 minutes. Cost to keep: about 1,000 tokens each quarter. The change deletes nothing.
