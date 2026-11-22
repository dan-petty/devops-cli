# Proposal: #6799

## Why

The test job of main fails since #6794 (#6736) merged after #6792 (#6729). Two tests of `tests/roadmap/refine/test_roadmap_refine_block_markers.py` find two refine sections. `closed_body` closes a block that the body leaves open at its end. The readers of #6736 end such an open block at the job blocks at its end. So when a job block is at the end of an open block of a person, the record write closes the block after the job block. The job block is then a quote, and the next refine round adds a second section. Closes #6799.

## What Changes

- `closed_body` in `src/devops_cli/roadmap/stores/store.py` first calls `close_blocks_before_markers` (#6736). That puts the close before the job blocks where the readers end the open block. Then `closed_body` closes a block that is still open at the end, as before.
- The round test of the open fence and the open `<pre>` now asserts one write that replaces the section in place. Its docstring asked for this change when a round reads the record.

## Capabilities

- `roadmap-item-labels`: the requirement "A record write closes the block that the body leaves open" says where the close goes when job blocks end the open block.

## Impact

A body with no open block keeps its text. A body that leaves a block open only at its end gets the same close as before. A body with job blocks at the end of an open block keeps each job block readable after a record write. The live check of #6736 found no open body of either kind on 2026-11-22.

## Feasibility

The failing run 45069872720 names the two tests. On 9dfe03e3e, a new unit test shows that the record write turns a job block in an open fence into a quote, and the round test finds two sections.

## Existing Tool Considered

None. The fix calls `close_blocks_before_markers` and `close_open_block` of `body_hash.py`, which use markdown-it-py. It adds no parser.
