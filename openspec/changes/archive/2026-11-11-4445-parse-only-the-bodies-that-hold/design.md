# Design

## Decisions

- **Skip the parse when the body does not hold the opening text.** `_RECORD_OPENER` is the text `<!-- devops-roadmap-record `, and `_RECORD_BLOCK` starts with it. `split_record` checks it with one substring search before the parse. The check is exact: a full match of `_RECORD_BLOCK` needs the text in the span, and the span is part of the body.
- **Parse only the blocks.** `_BODY_MARKDOWN` is `MarkdownIt("commonmark").disable("inline")`. `_record_block_span` reads the last top-level token, its type and its line map. The block parser makes these, and the core rule `inline` only fills the `children` of each `inline` token.
- **Keep the parser for the bodies that hold the text.** The parser rejects a quote of the block in a code span or a code block, and a comment that more text follows (#2538). The contract tests of the store hold these cases.

## Rejected alternatives

- **Also skip a body that does not end with `-->`.** A link reference definition at the end of a body makes no token, so a record block can be the last token of a body that ends with other text. This check would change the result for such a body. The substring check alone saves almost all of the time: it leaves 1,084 bodies to parse, and the end check leaves 1,082.
- **Find the record block with a regular expression and no parser.** A regular expression cannot see that a comment is inside a fenced or indented code block, which #2538 fixed.
- **Parse only the end of each body.** A fence that opens earlier in the body and does not close holds the rest of the body. Only a parse from the start sees it.
- **A faster Markdown parser, such as a Rust port of markdown-it.** It adds a dependency for a cost that the two exact checks already cut by about 3.6 times.
- **Keep the parsed records of the listing between runs.** It removes the parse for unchanged issues, but it needs a store of the listing on disk. #4404 files that work as its own item, which also cuts the GitHub read.
