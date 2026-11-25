# Proposal: #6177

## Why
The comment of `devops roadmap alternatives` shows at most five sources (`CONST_ROADMAP_ALTERNATIVES_MAX_COMMENT_SOURCES`). When the reply cites more, it shows the first five and the line "N more sources are left out". On 2026-11-17 the owner said that the jobs must have no hard caps that make a job fail or lose context. Refine, stage and implement read this comment as context, so the bound removes sources that they could read. Since #6174 (#6168), the sources are in the closed `<details>` block, so a long list does not make the open comment longer.

## What Changes
- The closed block of the comment lists every source of the reply.
- `CONST_ROADMAP_ALTERNATIVES_MAX_COMMENT_SOURCES`, its row in the table of limits, `_source_section` and the message `alternatives_comment_sources_left_out` go.

## Capabilities
- `roadmap-alternatives`: the requirement "The comment shows at most five sources" becomes "The comment shows every source".

## Impact
- A reply with more than five sources gets a longer closed block. The open part of the comment does not change.
- No setting, no command and no dependency changes. The change fits one pull request.

## Feasibility
- `git grep -n MAX_COMMENT_SOURCES origin/main` gives the one bound: `_source_section` in `src/devops_cli/roadmap/alternatives.py`, the constant in `src/devops_cli/config/constants.py`, its row in `tests/roadmap/test_roadmap_limit_classes.py`, and one test.
- No reader parses the sources or the "left out" line. The readers of the comment read its marker, and the refine prompt reads its text.

## Existing Tool Considered
None applies: the change deletes a bound in the render of the job. It adds no code.
