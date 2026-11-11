# Design

## Decisions

- **Add the `Requirement:` titles to the wanted headings.**: `section_text` already gives a section with its deeper headings, so each `### Requirement:` section comes with its `#### Scenario:` lines. The text keeps the order of the body: the problem statement, the `Acceptance criteria` heading, then each requirement.
- **Take every top-level `Requirement:` heading of the body.**: Only the refine block writes such headings in the issue bodies that the step reads. A requirement that a person writes in the same form is a criterion too.
- **Remove the comments with the parser, not with a pattern.**: In CommonMark, which GitHub uses, a block that starts with `<!--` is an `html_block` that ends at the line that holds `-->`. The token gives the line range. A comment in a code block is text, and it stays.
- **Remove the comments before the fallback too.**: An issue with neither section gives its whole body, and the markers of the refine and alternatives jobs tell the Coder nothing.

## Rejected alternatives

- **Change `section_text` to read on past a sibling `Requirement:` heading.**: `adr.py`, `step_rules.py`, `pull_describe.py`, `repair.py` and `implement_run.py` call it, and their sections end at the next heading of the same level by design.
- **Give the whole refine block.**: It also holds the key questions, the fit and the dependencies, which the proposal and design of the change already state. On #4004 the block holds 10,696 characters and its criteria 3,305.
- **Remove the comments with a regular expression.**: The project replaces hand-written patterns with parsers, and a pattern also removes a comment that a code block quotes.
