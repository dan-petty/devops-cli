# Design

## Decisions

- **One helper in the body hash module, `src/devops_cli/roadmap/body_hash.py:24:def extract_section_and_outside(`, finds a marker, and the four markers live in one set there.**: body_hash is imported by refine, the alternatives check, the repair pass and the stage job, so one rule serves the section ending, the block writing and the block reading, and two copies of the marker set cannot drift.
- **The helper returns the character span of a marker only where the marker is the whole text of an `html_block` token.**: markdown-it-py gives `html_block` tokens with a line map, and a marker in a code span, a fenced code block or a paragraph is another token, as the record block already reads at `src/devops_cli/roadmap/stores/store.py:952:if last is None or last.type != "html_block" or last.map is None:`.
- **The span is the text of the marker inside the block, not the whole line.**: The outside and inside slices of a real block stay byte for byte what they were, so the body hash that a job recorded for an existing item still matches.
- **The unpaired-marker guard counts only HTML-block markers.**: It follows the rule of #6613 that only an HTML block counts, so a quoted pair is the person's text and the check adds its block at the end.
- **A writer adds its block at the end of a body that holds no HTML-block marker pair.**: The alternatives spec says replace the block or add it at the end, and refine already builds its new body as the outside text plus its section at the end.
- **The stage criteria reader cuts the refine block with the same helper, at `src/devops_cli/roadmap/stage/stage_criteria.py:117:def _without_refine_block(`.**: That reader removes the block with `body.find`, so a quoted pair loses the criteria between the markers, and the expected behavior of the issue covers the readers of the block.
- **The marker set moves from the refine module to the body hash module under the name `JOB_BLOCK_MARKERS`, beside `src/devops_cli/roadmap/body_hash.py:43:def hash_text(`.**: refine imports body_hash, so body_hash cannot import refine, and one public set keeps the section ending and the block functions on the same rule.

## Rejected alternatives

- **One helper in body_hash with its own copy of the markers.**: Two copies of the marker set can drift, and the writer and the readers would then disagree on what a block is.
- **A separate parser in each module.**: It duplicates the CommonMark rule and lets the writer and the readers disagree.
- **A regular expression on the body.**: A regular expression cannot tell a code span, a fenced code block or a paragraph from an HTML block.
- **Keep the plain text search.**: A quoted pair would be refused as an unpaired marker, and the append of the issue's expected behavior would not happen.
- **Remove the unpaired-marker guard.**: A real start marker with no end marker would let a write replace the person's text.
- **Insert the block at the first quoted marker.**: It writes inside a person's code span and repeats the defect.
- **Write no block when the body holds no HTML-block marker.**: It leaves the item with no result from the job.
- **Require the `html_block` token to sit at the top level of the body.**: refine's section ending counts a marker at any level (#6613), and one rule for the section ending and the block functions must agree.

## Unchanged references

- `openspec/changes/archive/2026-11-21-6613-an-alternatives-block-names-no-blocker/design.md` (quoted target): An archived change records the design of #6613 as it was merged, and history is not rewritten.
- `openspec/changes/archive/2026-11-21-6613-an-alternatives-block-names-no-blocker/tasks.md` (quoted target): An archived change records the tasks of #6613 as they were merged, and history is not rewritten.
