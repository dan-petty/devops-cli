# Proposal: #6626

## Why
`acceptance_criteria` in `src/devops_cli/roadmap/stage/stage_criteria.py` keeps an open `Acceptance criteria` heading active through a following alternatives block because it removes only the refine block and ends the list only at the next heading. As a result, `Covers:` and `Lacks:` bullets inside the alternatives block become acceptance criteria, causing `criterion_problems` to refuse valid plans. Similarly, `implement_step.issue_inputs` removes HTML comments before calling `section_text` (`src/devops_cli/roadmap/step_files.py`), allowing alternatives text after the last section to leak into the step inputs.

## What Changes
- End an open `Acceptance criteria` section in `acceptance_criteria` (`src/devops_cli/roadmap/stage/stage_criteria.py`) when `block_marker_of` identifies a job block marker token.
- End open Markdown sections in `section_text` (`src/devops_cli/roadmap/step_files.py`) when `block_marker_of` identifies a job block marker token, and extract sections in `issue_inputs` (`src/devops_cli/roadmap/implement/implement_step.py`) before stripping HTML comments.
- Add regression tests in `tests/roadmap/stage/test_roadmap_stage_criteria.py` and `tests/roadmap/implement/test_roadmap_implement_step.py`.

## Capabilities
- `roadmap-stage/criteria`: stop reading an open `Acceptance criteria` section at a job block marker.
- `roadmap-implement-step/inputs`: stop reading issue sections at a job block marker before removing comments.

## Impact
- Prevents false missing-criterion plan refusals in `stage` when an alternatives block follows `Acceptance criteria`.
- Keeps alternatives block text out of matched sections passed by `implement_step.issue_inputs`.

## Feasibility
Confirmed against `origin/main` in `src/devops_cli/roadmap/stage/stage_criteria.py:231-250`, `src/devops_cli/roadmap/step_files.py:183-201`, and `src/devops_cli/roadmap/implement/implement_step.py:248-261`.

## Existing Tool Considered
Reuses `block_marker_of` from `src/devops_cli/roadmap/body_hash.py` (the rule established by #6613/#6627 for `refine.py`); no external library knows these internal job block marker conventions. Estimated cost to keep and maintain: about 5k tokens and under 1 hour.
