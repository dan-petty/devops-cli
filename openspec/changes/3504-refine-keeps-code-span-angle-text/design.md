# Design

## Decisions

- **Change the `<` of each tag outside code into `&lt;`, and leave the rest of the tag as it is.**: GitHub reads `<read command>` as an open tag with an attribute, and hides it with its words (see Feasibility). The entity makes the same characters show as text. The tag loses no word, and a reader of the section sees the placeholder.
- **A tag is a `<` followed by a letter or a slash, with no look for the closing `>`.**: The two characters are the start of an open tag and of a close tag in CommonMark. A `<` in `a < b` has a space after it and stays as it is. The look for a `>` would depend on where GitHub ends a tag, with its rules for quotes and line ends, and would cost time on a long text. A `<` that opens no tag shows as the same character with or without the entity, so an early escape does no harm.
- **Find the tags outside code with `_replace_outside_code`.**: The function already marks each match and reads the code that markdown-it shows, for links, handles and references (#2525). The tag step uses the same function, with `spans_are_code` false in a text that has a backtick that opens no code span. No new parse and no new regex for code are necessary.
- **Repeat the step until the text shows each tag in code (`_escaped_tags`).**: An escaped tag can hold a backtick. When the tag was raw HTML, markdown-it did not read that backtick. When the tag is text, the backtick opens or closes a code span, and the span takes a later tag in or out of code. The input ``<a title="`">`<b>` `` shows it: one pass leaves `<b>` raw. Each pass takes a `<` away, so the loop ends, and a text without a tag costs no parse.
- **Keep the comment opener step as it is, and run it before the tag step.**: The opener becomes `&lt;` also in code, because the record block and the markers are found in the raw text (#2478). The tag step takes only the `<` of a tag, so it builds no opener from the text around a tag. The old order (strip the tags, then neutralize the openers) is no longer necessary, and the test `A tag <<b></b>!-- rebuilt` pins the result.
- **Keep the end marker step as it is.**: The marker of the section ends the section in the raw text, in code or not.
- **Compute `shortest` and `stray` again after the tag step.**: The escape shows backticks that a raw tag hid, so the run lengths and the stray state of the final text can differ from those before it.
- **Test the result with a property.**: The property shows that the sanitized text holds no `html_inline` and no `html_block` token, for texts made of backticks, tags, comment openers and block marks. The example found in the first version is a fixed case of the test.

## Out of scope

- **A section that refine already wrote.**: The issue says this change does not repair it. The next refine round writes the section again.
- **The stage and alternatives callers.**: They call the same function, so their text gains the same rule. The change adds no option for them.

## Rejected alternatives

- **Strip a tag only outside code.**: The words of `use <read command> here` are lost, and the issue asks that no word be lost.
- **Escape every `<` of the text, also in code.**: A code span would then show `&lt;` as text, and `<section>.<option>` would not stay as it is.
- **Clean the HTML with a library such as `nh3` or `bleach`.**: These libraries work on HTML and remove tags and attributes, so they lose the words of a tag. They have no notion of a Markdown code span.
- **Escape in one pass.**: A search with `hypothesis` finds a text that keeps a raw tag after one pass (see Feasibility).
- **Match the whole tag with `<[a-zA-Z/][^>]*>` and escape its opener.**: It needs the closing `>`, which GitHub finds by rules that the regex does not copy, and each `<` without a `>` after it scans to the end of the text.
