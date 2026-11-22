# Proposal: #6785

## Why

A job writes the record block at the end of the issue body. `split_record` reads the record only when CommonMark parses the last top-level block as an HTML block that holds only the record. A person can later open a fenced code block, a `<pre>` block or a comment above the record and not close it. The record is then part of that block, and `split_record` reads an empty record. The item loses its job state: the hashes of refine and alternatives, and each stop of implement. When the open block is above the refine block, the next record write closes the block before the refine block (#6799). The old record is then a stale copy above the new record, and its keys are lost. Closes #6785.

## What Changes

- `split_record` in `src/devops_cli/roadmap/stores/store.py` also reads the record block on the last line of the body, when that line is a record block of its own and ends a block that the body opens above it. `close_open_block` of `body_hash.py` decides that the block is open, which is the rule of the job block readers (#6736). The parse runs only when the last block is not the record.
- A line in an open block that holds no JSON object stays the text of the person, with no warning.
- The next record write closes the block before the record (`closed_body`, #6729), and it writes one record block with the keys of the old record.
- `docs/ROADMAP_WORKFLOW.md` says that the read ends an open block at the record.

## Capabilities

- `roadmap-item-labels`: the requirement "Only the comment at the end of the body is the record block" also reads the record on the last line of a block that a person opens above it.

## Impact

A body whose last block is the record reads as before, with one parse. A body that does not hold the record opener is not parsed (#4445). On 2026-11-22, the code of origin/main read the record of each of the 835 open issues of 837 that hold the record opener. So no item has the defect now, and the change gives each of them the same body and record. The change fits one pull request.

## Feasibility

A script on b1d485234 writes a record with `with_record` and then opens a block in the text of the person. `split_record` gives `{}` for a backtick fence, a tilde fence, a `<pre>` block and a comment. With a fence above the refine block and the record, the next write gives a body with two record blocks. The script also shows that CommonMark (markdown-it-py) parses the edited body as one `fence` or `html_block` that runs to the end of the body.

## Existing Tool Considered

markdown-it-py parses the body, as before. The change adds no parser and no end rule of CommonMark. It uses `close_open_block` of `body_hash.py`, whose probe decides which block is open for the job block readers. The change deletes no code: the cut of the separator moves into a helper that both reads use.
