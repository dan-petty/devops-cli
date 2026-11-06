# Design

## Decisions

- **Change the `<` of each tag outside code into `&lt;`, and leave the rest of the tag as it is.**: GitHub reads `<read command>` as an open tag with an attribute, and hides it with its words (see Feasibility). The entity makes the same characters show as text. The tag loses no word, and a reader of the section sees the placeholder.
- **A tag is a `<` followed by a letter or a slash, with no look for the closing `>`.**: The two characters are the start of an open tag and of a close tag in CommonMark. A `<` in `a < b` has a space after it and stays as it is. A look for the `>` depends on how GitHub ends a tag, with its rules for quotes and line ends. It would also cost time on a long text. A `<` that opens no tag shows as the same character with or without the entity, so an early escape does no harm.
- **Leave a `<` that an odd number of backslashes escapes.**: GitHub shows `\<b>x` as the text `<b>x`. The entity after the backslash would show as the text `&lt;b>x` (see Feasibility). The regex of the tag opener takes only a `<` with an even number of backslashes, or none, before it.
- **Find the tags outside code with `_replace_outside_code`.**: The function already marks each match and reads the code that markdown-it shows, for links, handles and references (#2525). The tag step uses the same function. `spans_are_code` is false in a text that has a backtick that opens no code span. No new parse and no new regex for code are necessary.
- **Repeat the step while the text changes, with at most three passes (`_escaped_tags`).**: An escaped tag can hold a backtick. When the tag was raw HTML, markdown-it did not read that backtick. When the tag is text, the backtick opens or closes a code span, and the span takes a later tag in or out of code. The input ``<a title="`">`<b>` `` shows it: one pass leaves `<b>` raw. Each pass parses the whole text, so a repeat without a bound takes time with the square of the length.
- **After three passes, change each tag, also in code.**: A text that three passes do not settle is hostile. The change in code costs a code span its `<`, and one `re.sub` ends in linear time. A text that a person writes needs one pass, and two when a tag holds a backtick.
- **Skip the parse when the text holds no tag opener.**: `_escaped_tags` first searches for the opener with the regex, so it parses no text without a tag.
- **Keep the comment opener step, and run it before the tag step.**: The opener becomes `&lt;` also in code, because the record block and the markers are found in the raw text (#2478). The tag step takes only the `<` of a tag, so it builds no opener from the text around a tag. The test `A tag <<b></b>!-- rebuilt` pins the result.
- **Look for tags and openers again after the rewrite of the links.**: The rewrite drops the `[` and the `](` of a label. So `<[b>](https://example.com/a)` gives `<b> (...)`, and a label `!-- devops-roadmap-record ... --` gives a forged opener. The look after the rewrite is a second call of `_without_raw_html`, which costs no parse when no opener is left. The step for the images runs first, for the same reason.
- **Keep the end marker step as it is.**: The marker of the section ends the section in the raw text, in code or not.
- **Compute `shortest` and `stray` after the first look for tags.**: The escape shows backticks that a raw tag hid. So the run lengths and the stray state of the text can differ from those before it. The second look changes no backtick count, and the fence lengths of the link step stay valid.
- **Keep each tag in a title: `safe_title`, with the keyword `escape_tags` of `sanitize_text`.**: A title is plain text (see Feasibility). `staging_title`, `delivery_title` and the check of the summary use `safe_title`. The comment opener stays an entity, because the job puts a title in a comment. A handle or a link in a title stays in a code span, as before.
- **Test the result with a property.**: The property shows that the sanitized text holds no `html_inline` and no `html_block` token. The texts are made of backticks, tags, comment openers, link syntax, backslashes and block marks. The examples found in review are fixed cases of the test.

## Out of scope

- **A section that refine already wrote.**: The issue says this change does not repair it. The next refine round writes the section again.
- **The stage and alternatives callers.**: They call the same function, so their text gains the same rule. The change adds no option for them, except the title functions.
- **A release-please changelog line with a tag word.**: Release-please already escapes it.

## Rejected alternatives

- **Strip a tag only outside code.**: The words of `use <read command> here` are lost, and the issue asks that no word be lost.
- **Escape every `<` of the text, also in code.**: A code span would then show `&lt;` as text, and `<section>.<option>` would not stay as it is.
- **Clean the HTML with a library such as `nh3` or `bleach`.**: These libraries work on HTML and remove tags and attributes, so they lose the words of a tag. They have no notion of a Markdown code span.
- **Escape in one pass.**: A search with `hypothesis` finds a text that keeps a raw tag after one pass (see Feasibility).
- **Repeat until the text is stable, with no bound.**: A hostile text takes seconds (see Feasibility).
- **Match the whole tag with `<[a-zA-Z/][^>]*>` and escape its opener.**: It needs the closing `>`, which GitHub finds by rules that the regex does not copy. Each `<` without a `>` after it scans to the end of the text.
- **Keep the entity in a title.**: GitHub shows it as the text `&lt;`, the squash commit holds it, and each tag adds three characters to the count of the check `Semantic PR title`.
- **Narrow the spec and file the hole of the link rewrite.**: The fix is one more call of a function that exists, so the claim "no raw HTML" holds.
