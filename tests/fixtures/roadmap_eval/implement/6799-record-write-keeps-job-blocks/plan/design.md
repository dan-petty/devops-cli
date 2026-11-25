# Design

## Decisions

- `closed_body` calls `close_blocks_before_markers` first, then the old close of the end. Reason: the readers end an open block at the job blocks at its end, so the write must close it there too. One rule then decides the reads and the writes.
- The import of `close_blocks_before_markers` stays inside `closed_body`, as the import of `close_open_block` does. Reason: `body_hash.py` imports `store.py`.
- The two lost-edit checks of the GitHub store need no change. Reason: they compare with `closed_body`, so they accept the new close.

## Rejected alternatives

- A revert of #6792 or #6794. Each fix is correct alone, and only the order of the two closes was wrong.
- A skip of the failing tests. The tests show a real defect: a second section in the body.
