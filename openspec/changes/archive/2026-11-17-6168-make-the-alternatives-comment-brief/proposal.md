# Proposal: #6168

## Why
The comment of `devops roadmap alternatives` is too long to read quickly. The owner asked on 2026-11-17 for a brief and concise comment. The comment on #5384 has 2,210 characters, and the comment on #5398 has 1,585 characters. Two sources make it long.

1. The prompt asks for a reason of "one or two sentences" and sets no size for `covers`, `lacks` and `sources`. The model writes 2 or 3 long sentences and items of 15 to 25 words.
2. The render shows a "Tools considered" list, a "Searches run" list of up to 10 lines, a tool block of 4 lines and a footer of two sentences. For `not-applicable` it shows three lines that say little.

## What Changes
- The prompt `roadmap_alternatives.md` asks for a reason of one sentence of about 30 words, and a few items, about 3, in `covers`, `lacks` and `sources`. Each item is a plain phrase of about 12 words with no filler. This is guidance only: the schema of the reply sets no length, and the job refuses no reply for its length and cuts no text of it (owner, 2026-11-17).
- The comment shows the tool on one line, the same line as the block of the body.
- One `<details><summary>Searches (N)</summary>` block, which GitHub shows closed, holds the tools considered, the answered searches and the sources. Nothing is left out of it.
- The footer is one sentence.
- The comment of a skip class is one line: `Alternatives check: not-applicable (<class> item; no search).`
- The marker, the heading `## Alternatives check: <verdict>`, `Reason:`, `Covers:`, `Lacks:`, `Tool: none found` and the block of the body stay as they are.

## Capabilities
- `roadmap-alternatives`: the comment requirements and the skip-class requirement change.

## Impact
- On the open page of GitHub, the comment of #5384 drops from 2,210 to 1,259 characters with the same text of the model, and to about 700 characters with a reply that follows the new prompt. The folded block keeps the rest. The comment of a skip class drops to one line.
- Refine, stage and implement read the comment and the block. The marker and the block do not change. The comment keeps `Covers:` and `Lacks:`, which the refine prompt reads.
- No setting, no command and no dependency changes. The change fits one pull request.

## Feasibility
- `devops gh api repos/dan-petty/devops-cli/issues/5384/comments` and `.../5398/comments` give the two comments with the marker `<!-- devops roadmap alternatives -->`, of 2,210 and 1,585 characters.
- The readers of the comment:
  - `_latest_check_comment` and `covers_question` in `src/devops_cli/roadmap/refine/refine.py` read the marker, through `replies_after_marker`.
  - `_request` in `src/devops_cli/roadmap/alternatives.py` reads the marker.
  - `COMMENT_JOBS` in `src/devops_cli/roadmap/stores/comment_repeat.py` reads the marker.
  - The refine prompt `roadmap_refine_proposal.md` reads what the tool lacks, "as the `comment` states".
  - `recorded_check` reads the block of the body, which does not change.
- No code parses a line of the comment other than the marker.
- GitHub renders Markdown inside `<details>` when a blank line follows `<summary>`.

## Existing Tool Considered
The `<details>` element of GitHub Markdown folds the evidence, so the change needs no new tool. The rest is the text of one prompt and one render function.
