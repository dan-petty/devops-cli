# Design

## Decisions
- Use `block_marker_of` from `src/devops_cli/roadmap/body_hash.py` in both `acceptance_criteria` (`src/devops_cli/roadmap/stage/stage_criteria.py`) and `section_text` (`src/devops_cli/roadmap/step_files.py`) so every section reader applies one CommonMark HTML-block marker boundary rule.
- Call `section_text` on `item.body` in `issue_inputs` (`src/devops_cli/roadmap/implement/implement_step.py`) before `_without_comments` strips HTML comments, so `section_text` sees the job block markers while preserving existing fallback behavior when no section matches.

## Rejected alternatives
- **Call `without_alternatives` globally in `stage_criteria.py` and `section_text`**: duplicates block-stripping logic and does not terminate an open section at an arbitrary job block start marker.
- **Match headings inside the alternatives block**: the alternatives block contains no headings, so heading matching misses its boundary.
