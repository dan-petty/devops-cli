# Design

## Decisions

- **A block that no close ends ends at its first job block marker line.**: A fenced code block or an HTML block of kinds 1 to 5 with no close runs to the end of the body. GitHub then shows each later line as code, the job blocks too. So such a block is open by accident. The first line in it that CommonMark reads as a job block marker on its own ends it for a read. Before #6720, the plain text search replaced the old block in place. The read of #6627 leaves two start markers (Feasibility).
- **Any job block marker ends the open block, not only the markers of the reader.**: Each reader must see the same blocks. With only its own markers, the alternatives write would close the fence after a refine section that comes first. That section would then be a quote in a closed fence, and refine would write a second one.
- **The parser tells whether a block is open.**: `_open_block` parses the last block with the probe marker after a blank line, as `close_open_block` does. When the probe is part of that block, the block is open. A rule of our own for the end of each block kind would copy CommonMark.
- **`extract_section_and_outside` cuts the body with the closes in place (`close_blocks_before_markers`).**: The refine write and the repair pass keep the outside text. So they write the close before the job block and keep the next block readable. A body with no open block above a marker does not change, so no recorded hash changes.
- **`block_marker_of` is the one token test.**: `_marker_span` and `_ends_section` both call it, so a comment that a person leaves open above a job block ends a section too.
- **`body_dependencies` parses the body with the closes in place.**: It reads the Dependencies part of the refine section, so it must find that section where the other readers find it.
- **A marker in a block that a close ends stays a quote.**: A person who quotes a job block in code closes the fence. The tests of #6627 for a quoted pair stay green.
- **A lone marker in an open block stops the alternatives write.**: The open block ends at that marker, and the marker has no partner, so `_marker_problem` names it. This is the rule for an unpaired marker of #6627.
- **The body parser of `body_hash` reads only the blocks (`disable("inline")`).**: The rule reads only `html_block` and `fence` tokens, as the record parser of `src/devops_cli/roadmap/stores/store.py` does. The probe of an open block adds a parse, and the parse without inline rules costs about half the time.
- **The refine round test asserts one section and a body that does not change, not the number of model calls.**: The record block is the last block of the body, so the open block of a person holds it too, and `split_record` then reads no record. Refine then finds a section that it has no record of, and waits for a person. A run with a `with_record` that closes the open block only at the end of the body gave two sections. A run with a `with_record` that first calls `close_blocks_before_markers` gave one. The record is the work of #6729, and this change does not touch `src/devops_cli/roadmap/stores/store.py`.
- **This decision replaces the rejected alternative "Close the open block before the first marker line in it" of #6627, for a block that no close ends.**: #6736 expects one block after each write. A block in a closed fence is still a quote.

## Rejected alternatives

- **Read a marker in an open block as an unpaired marker and write no block (option b of the review of PR #6720).**: Refine has no such stop. The item then gets no result from a job until a person closes the block.
- **Read each whole-line marker in any code block or HTML block as a bound.**: A quoted pair in a closed fence would then lose its text. `test_a_marker_in_a_code_span_a_code_block_or_a_paragraph_is_no_block` forbids it.
- **Keep the close at the end of the outside text.**: The premise script shows two start markers after each round.
- **Close the open block only in each writer, and keep `extract_section_and_outside` a plain cut.**: Each writer must then repeat the call. The repair pass would write an alternatives block back into the open block.
- **Use the recorded section hash to accept a marker in an open block.**: The alternatives job records no hash of its block, and the readers take no item.
