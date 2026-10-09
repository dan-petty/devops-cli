# Task: A web_fetch budget cut inside a code block closes the fence before the truncation note and boundary tag (#1298)

**Issue**: [#1298](https://github.com/dan-petty/devops-cli/issues/1298)
**Status**: Done
**Milestone**: v0.2.30
**Priority**: priority/p2-medium
**Scope**: type/bug, scope/ai

## Description

`_apply_blank_line_cut` in `src/devops_cli/ai/common_tools.py` cut the rendered Markdown at the latest blank line or newline within the budget, without regard to fences. A cut inside a `<pre>` block left its fence open, so the truncation note and the closing `</untrusted_web_page>` tag landed inside the code block. Page text still could not forge the boundary, and the tag stayed the last line of the tool result, so this is hardening. It came in with #896.

The cut point is chosen as before. The function then parses the text with markdown-it-py (already a dependency, imported locally as in `roadmap/close.py`) and finds the fenced block that holds the cut line:

- A cut inside the block keeps the block's own closing line, which carries the fence length and any container prefix (blockquote `>`, list indent). That line may exceed the budget by its length.
- A cut on the block's opening line drops the block.

The function first normalizes `\r\n` and a lone `\r` to `\n`, CommonMark's line endings, so markdown-it's line numbers index `text.split("\n")`. markdownify keeps a lone `\r` in `<pre>` content and in link titles. Without the normalization the two line counts disagree after such a line: the closing line lookup raises `IndexError` or appends a stray fence that opens a new block. Lines come from `split("\n")`, not `splitlines()`, which also splits on characters markdown-it does not treat as line breaks.

## Acceptance Criteria

- [x] A cut inside a fenced block closes the fence, using markdown-it-py, before the truncation note and the boundary tag. `test_render_untrusted_page_budget_cut_inside_code_block_closes_the_fence` in `tests/test_common_tools.py` parses the result and finds neither the tag nor the note inside any fence: a block after a paragraph, a block that starts the page (cut mid-listing, on the opening line, and part way through the opening line), a block in a blockquote, a block in a list item, and a block after `\r` line endings.
- [x] `changelog.d/1298.md` records the change; `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] `uv run devops ci` passes.

## Deliverables

- [x] `src/devops_cli/ai/common_tools.py`: `_apply_blank_line_cut` normalizes line endings and closes a fence the cut falls inside, or drops the block when the cut falls on its opening line.
- [x] `tests/test_common_tools.py`: `test_render_untrusted_page_budget_cut_inside_code_block_closes_the_fence`.
- [x] `changelog.d/1298.md`: changelog entry for #1298.
- [x] `docs/agent/tasks/task-1298-web-fetch-cut-closes-open-fence.md`: this task file.
