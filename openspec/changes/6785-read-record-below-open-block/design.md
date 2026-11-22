# Design

## Decisions

- **Read the record on the last line only when the last block is not the record.**: `split_record` runs for each issue of a listing. A body that does not hold the record opener is not parsed (#4445), and a body whose last block is the record gets one parse, as before. Only a body with the opener whose last block is not the record gets the parse of its last line and the probe of the text before it.
- **Let `close_open_block` of `body_hash.py` decide that a block is open above the record line.**: The job block readers end an open block at the job blocks at its end, and their probe decides which block is open (#6627, #6736). The probe is a one-line comment after a blank line, as the record block is. So CommonMark ends the same blocks at the probe and at the record line: a comment and a declaration end at that line, and a fence and each other HTML block that only an end text ends run past it. One rule then decides both reads, with no second parser and no end rule of CommonMark in the store.
- **The last line is a record block only when CommonMark parses the line alone as an HTML block.**: The job block readers of #6736 test each marker line in the same way. A job writes the record with no indent, so an indented quote stays the text of the person.
- **A record line in an open block that holds no JSON object stays the text of the person.**: A job always writes a JSON object. A broken record that is the last block reads as an empty record, and the next write replaces it. In an open block, such a line is more likely a quote of a person, and the requirement keeps a quote in a code block with no warning.
- **The writer's separator goes with the record, as before.**: The read gives the text of the person without the record block. The next write is `closed_body` of that text, a blank line and the record block, so the body holds one record block with the keys of the old record.
- **Require no blank line before the record line.**: The job block readers of #6736 require no blank line before a marker line in an open block. A person can put the opener of the block on the line directly above the record.
- **No change in the GitHub store.**: The body of the Item is the text of the person without the record. The read-back of the write is `closed_body` of that text, which both lost-edit checks of `_edit_issue` accept (#6729).
- **Import `close_open_block` inside the function.**: `body_hash.py` imports `store.py`, so an import at the top of `store.py` makes a cycle. `closed_body` uses the same form.

## Rejected alternatives

- **Add the record line to the job block markers of `_parts` in `body_hash.py`.**: The record block is no job block. `_parts` parses each part again and tests each marker line, so each body of a listing with an open block costs more parses. The readers of the job blocks get the body without the record, so they need no change.
- **Close the open block when the store reads the body.**: The read then gives a body that GitHub does not hold, and the lost-edit check of the GitHub store sees a change on each write. #6729 rejected this for the same reason.
- **Find the record opener anywhere in an open block.**: A quote of the record in the middle of a fence of a person would then read as the record. The job writes the record only at the end of the body.
- **Warn and drop a record line in an open block that holds no JSON object, as for the last block.**: The read would then take a quote of a person out of the body, and the next write would lose it.
