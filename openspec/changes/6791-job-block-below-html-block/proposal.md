# Proposal: #6791

## Why

CommonMark ends an HTML block of kind 6 or 7 only at a blank line. Kind 6 starts with a block tag such as `<details>`, `</details>` or `<div>`. Kind 7 is a whole tag on a line of its own, such as `<img src="...">`. A person can remove the blank line between such a line and a job block marker or the record line. The marker or the record is then part of that HTML block.

So `job_block_bounds` and `extract_section_and_outside` find no job block, and the next refine or alternatives write adds a second block. `split_record` reads no record, so the next record write adds a second record. The item then loses the keys of the old record (comment of 2026-11-23). Closes #6791.

## What Changes

- In `src/devops_cli/roadmap/body_hash.py`, a job block marker line can end a top-level HTML block that only a blank line ends. The line must start the job blocks at the end of the body, as in a block that a person leaves open (#6736). No text may follow these blocks, and the cut must leave no block open. `_parts` starts a new part at that line (`_html_block_end`). Each job block reader uses `_parts`, so one rule decides each read.
- Each other marker line in such a block stays the text of the person. So a write keeps that block as it is.
- `close_blocks_before_markers` writes a blank line before the marker line that ends the block. So the refine write, the alternatives write and the record write keep the next block readable.
- The new function `ends_at_a_blank_line` tells these kinds of HTML block by the table `_HTML_BLOCK_CLOSES`. No end text of that table starts them.
- `split_record` in `src/devops_cli/roadmap/stores/store.py` reads the record on the last line of the body when that line is in such a block. The next record write puts a blank line before the record.
- `docs/ROADMAP_WORKFLOW.md` states the rule for the record.
- The change alters the body that a job writes and the record that the store reads, so it carries spec deltas.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine/writes`: The hash of the body leaves out the job's block
- `roadmap-alternatives`: A marker bounds a block only as an HTML block
- `roadmap-item-labels`: Only the comment at the end of the body is the record block

## Impact

- Code: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/stores/store.py`
- Tests: `tests/roadmap/test_roadmap_body_hash.py`, `tests/roadmap/refine/test_roadmap_refine_block_markers.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/stores/test_roadmap_store_record_block.py`
- On 2026-11-23, a census script read the 833 open issue bodies with markdown-it-py. Their 276 HTML blocks of kind 6 or 7 hold no job block marker line and no record line. So no read of a live item changes.

## Feasibility

- A scratch script ran on `origin/main` (`c7e40970d`). With `</details>` or `<div>x</div>` directly above the refine start marker, `job_block_bounds` gave None and `extract_section_and_outside` gave no section. With a blank line between, both found the block. With `<details>` or `<div>` directly above the record line, `split_record` gave `{}`.
- CommonMark 0.31.2, section 4.6, gives the end condition of kinds 6 and 7: a blank line. markdown-it-py 4.3.0 (`uv.lock`) follows it. The body `</details>`, refine start marker, `checked-at` line, `## Proposed design` gives one `html_block` token over the four lines.

## Existing Tool Considered

markdown-it-py (https://pypi.org/project/markdown-it-py), MIT License, maintained, and already in use in `src/devops_cli/roadmap/body_hash.py`. Its tokens tell the HTML block and its lines. The alternatives check of the issue named the same tool. The change adds no parser, no dependency and no end rule of CommonMark. The table `_HTML_BLOCK_CLOSES` already tells kinds 1 to 5, and each other HTML block is of kind 6 or 7. The change deletes no code.
