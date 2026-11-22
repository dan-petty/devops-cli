# Proposal: #6736

## Why

The review of PR #6720 (#6627) found two cases where a job block reader does not use the marker rule of `src/devops_cli/roadmap/body_hash.py` (#6736).

1. A person opens a code fence or a `<pre>` block above a job block and does not close it. CommonMark then reads the old block as code, so the read does not find it. The refine write and the alternatives write close the open block after the old block and add a second block. The old block stays in the body as code.
2. `_ends_section` in `src/devops_cli/roadmap/refine/refine.py` ends a section only at an HTML block whose whole text is a marker. A comment that a person leaves open above an alternatives block ends at the start marker, so `body_dependencies` reads the Lacks list of the block as blockers of the item.

## What Changes

- `src/devops_cli/roadmap/body_hash.py` gets `block_marker_of`, the one token test for a job block marker. `_marker_span` and `_ends_section` use it.
- A fenced code block or an HTML block that no close ends runs to the end of the body. In such a block, the first line that is a job block marker on its own ends the block for a read. `block_marker_spans` and `job_block_bounds` read the body in that form.
- `close_blocks_before_markers` writes the close of such a block on a line of its own before that line. `extract_section_and_outside` cuts the body in that form, so refine and the repair pass write the close before the job block. The alternatives `_with_block` uses the same function.
- `body_dependencies` parses the body in that form.
- A marker in a block that a close ends stays the text of the person.
- The change alters the body that a job writes and the blockers that refine reads, so it carries spec deltas.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine/writes`: Refine replaces its section in a block that a person leaves open
- `roadmap-refine/waits`: A job block marker ends the Dependencies section
- `roadmap-alternatives`: A check replaces its block in a block that a person leaves open

## Impact

- Code: `src/devops_cli/roadmap/body_hash.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/alternatives.py`
- Tests: `tests/roadmap/test_roadmap_body_hash.py`, `tests/roadmap/refine/test_roadmap_refine_dependencies.py`, `tests/roadmap/refine/test_roadmap_refine_block_markers.py`, `tests/roadmap/test_roadmap_alternatives.py`

## Feasibility

- A scratch script ran on `origin/main` (`a3e30286e`). It imports only `src`. Over three rounds of the refine write path (`extract_section_and_outside`, then `close_open_block` at `src/devops_cli/roadmap/refine/refine.py:3721`) and of `_with_block` (`src/devops_cli/roadmap/alternatives.py:1096`), a body with an open fence or an open `<pre>` above an old block gave the start marker counts `[2, 2, 2]` in each of the four cases.
- The same script gave `body_dependencies` = `[4989, 5506]` for the body of case 2. `_ends_section` (`src/devops_cli/roadmap/refine/refine.py:1166`) tests `token.content.strip() in JOB_BLOCK_MARKERS`, and `_bounding_marker` (`src/devops_cli/roadmap/body_hash.py:62`) also accepts the last line of a comment.
- The CommonMark spec 0.31.2 says that a fenced code block with no closing fence runs to the end of the document or of its container, and that an HTML block of kinds 1 to 5 runs to its end condition or to the end of the document. markdown-it-py 4.3.0 (`uv.lock`) follows it: the prototype parse of the bodies above gave one `fence` or `html_block` token to the end of the body.

## Existing Tool Considered

markdown-it-py (https://pypi.org/project/markdown-it-py), MIT License, maintained, and already in use in `src/devops_cli/roadmap/body_hash.py`. The change asks the parser whether a block is open, with the probe that `close_open_block` already uses, and adds no parser and no dependency. It deletes the token test of `_ends_section`, a second copy of the marker rule.
