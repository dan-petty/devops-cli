# Design

## Decisions

- **Read the text from the code span that follows the citation only when the text up to the next backtick is empty.**: A citation in one span, `path:line:text`, keeps its meaning. The new reading applies to the one form where the old reading finds no text at all.
- **Allow the closing backtick of the citation and white space before the span of the text.**: A plan writes both `path:12: `text`` and `path:12:` `text``.
- **Compare the text with the line as before.**: The text must still be a part of the cited line and have at least 3 characters.

## Rejected alternatives

- **Change the prompt to ask for one span only.**: The gate would still refuse the other reading of the same sentence, and a change of the prompt invalidates every kept plan.
- **Accept the text when it is on another line of the file.**: A line number that the file does not hold is the defect that #3422 made the check for.
