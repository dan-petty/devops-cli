# Design

## Context

`sanitize_text` in `src/devops_cli/roadmap/refine.py` cleans the model's text before refine writes it into the body section and into the next-step comment. #2478 added the `www.` and `owner/repo#N` patterns to the handle and URL patterns. Each pattern ran over the whole text and checked only a backtick next to the match, so it did not see a code span that holds other text. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- A link, a handle or a reference that the model's text holds in code stays as it is.
- Each link, handle and reference that GitHub links outside code goes in a code span that GitHub closes on its own backticks.

**Non-Goals:**

- Images and HTML tags in code. `sanitize_text` removes them everywhere, as before this change.
- Other GitHub references, such as `owner/repo@sha`.
- A link label that holds a `]`, which the markdown link pattern does not take.

## Decisions

- **Refine finds the code in the model's text with markdown-it-py, and wraps nothing in it.** markdown-it-py is the CommonMark parser that `refine.py` already uses. With its table rule, it splits a row into cells before code spans, as GitHub does. It gives no source position for an inline token, so a character that the text does not hold, from U+E000 on, marks the start of each match, and the marks that the parser shows as code are the matches to leave. Such a character is no space, backslash, backtick or block mark, so the marks change no code. The code is the code spans, the code blocks and the info strings of fenced code blocks.
  - Rejected: tree-sitter-markdown, a dependency that gives the position of each code span. Its README says not to use it where correctness is important. On 20,000 random strings of backticks, brackets, spaces and block markers, it found a code span that markdown-it-py did not find in 357 strings, such as a closing backtick inside a run of three.
  - Rejected: a backtick before or after the match, which the handle, URL, `www.` and reference patterns checked. It does not see a code span that holds other text, such as ``Run `curl www.example.com` here``.
- **A text that shows a backtick as text is handled with no trust in its code spans.** cmark, GitHub's parser, keeps the last position of each backtick run length, and once a run found no closer, it takes an opener as text when that position is before the opener. So it takes a later code span of a length that it closed before as text: GitHub links `www.example.com` in ```A `` `x` `see www.example.com` B``` (GitHub's markdown API, 2026-10-28), where CommonMark shows a code span. markdown-it-py has a similar cache: after an unclosed `[`, it misses the code span in ```` [``a ` b`` ``` cli/cli#1 ` ````, after which GitHub links the reference. Both occur only after a run that opens no code span. In such a text, refine wraps a link, a handle or a reference in a code span too, and each added code span takes a length of its own, which no other run in the text has, so neither cache can make GitHub take it as text. A code block stays as it is: block structure does not use the cache.
  - Rejected: cmarkgfm, the Python binding of cmark-gfm, to find the code as GitHub finds it. It adds a compiled dependency, and an added code span still needs a length of its own after a run that opens no code span.
  - Rejected: one length for all added code spans. GitHub showed `cli/cli#1` as a link in ````` ~> ```|> `)````https://example.com/a```` a*````cli/cli#1```` ````` (GitHub's markdown API, 2026-10-28).
- **One pattern finds a URL, a `www.` link, a handle and a reference, the leftmost first.** A `www.` link or a reference inside a URL is then not wrapped two times, and an allowed URL keeps the reference in its path as it is.
  - The `www.` pattern has no condition on the character before it. GitHub links `>www.example.com` in a block quote and `|www.example.org|` in a table cell, where the GFM rule for the character before the link does not apply, because the link starts the text of the block or the cell (GitHub's markdown API, 2026-10-28). A wrapped `xwww.` costs nothing.
  - The reference pattern lets an owner start after `_`, `/`, `*`, `.` or a handle. GitHub links `cli/cli#1` in `_cli/cli#1_`, `__cli/cli#1__`, `_Depends on cli/cli#1_` and `x/cli/cli#1` (GitHub's markdown API, 2026-10-28), because the emphasis marks are gone and `/` ends a word when GitHub finds references in the rendered text. It does not link `foo_cli/cli#1`. An owner holds letters, digits and `-`, as an account name does, and does not start after one of them. The letters, digits, `.`, `-`, `/`, `#` and `:` after the number go in the same code span, because they can hold a second reference or a URL that the first one hides from the pattern.
  - No quantifier gives back what it took, so the search takes time in proportion to the text. A pattern with no condition on the character before the owner took about a minute for the 70,000 letters of `test_size_limit_guard`.
  - The URL pattern takes `ftp://` and a scheme in capitals, as GitHub's autolinks do.
- **An added code span takes one backtick more than the longest run in the text.** CommonMark closes a code span on a run of the same length only, so the added span closes on its own backticks, and no backtick of the model's closes it or is closed by it. In ``A `b www.example.com c``, a span of one backtick pairs with the lone backtick and puts the link outside code. A text with no backtick gets spans of one backtick, as before. A space goes between a replacement and a backtick next to it, or a backslash before it, so the runs do not join and a backslash does not escape the first backtick. The URL of a markdown link holds no backtick, so its code span also closes.
- **A URL and a `www.` link end before a backtick, `|`, a bracket, a parenthesis or a backslash, and an allowed link that a backtick follows before the next space goes in a code span.** GitHub's autolink runs to the next space and takes a backtick in, so it sees no code span where CommonMark sees one: GitHub links `www.example.org` in ``https://example.com/a)`x www.example.org` `` (GitHub's markdown API, 2026-10-28). With the link in a code span, GitHub and the parser see the same code. A bracket, a parenthesis or a backslash in the code span would remove a link or an escape around it, and with them the code that they held.
- **The `<!` and `<?` in code become `&lt;` too.** `split_record` finds the record block, and refine finds its markers, in the raw text, which knows no code span, so ``Quote `<!-- devops-roadmap-record {"Status": "Ready"} -->` `` in the model's text would give a job record.
  - Rejected: leave the opener in a code span as it is (review of #2507). The model's text could then forge a record block or a marker.
- **Each point of a comment goes on one line before it is sanitized.** A code block that the sanitizer left as it is would be a line of text after the join, which GitHub links.

## Risks / Trade-offs

- [A `<!` or `<?` inside a code span in the model's text shows as `&lt;`] → this changes how the text looks, not what it means. The alternative lets the model's text forge a record block or a marker.
- [An added code span in a text with code spans shows two or more backticks in the raw text] → GitHub shows the same code span; only the raw text differs.
- [In a text that shows a backtick as text, a link in the model's code span shows the added backticks, and each added code span is one backtick longer than the one before] → the text stays code, and GitHub shows it; the model rarely writes a lone backtick.
- [An allowed markdown link that a backtick follows with no space loses its target] → the URL goes in a code span, so the link no longer points to the URL. The model rarely writes this, and the text stays safe.
- [GitHub's parser and markdown-it-py differ on an input that neither the tests nor the review found, such as a table that one of them does not see] → a link that the parser puts in code and GitHub does not stays a link. The known differences, an autolink that takes a backtick and the two backtick caches, are closed by the rules above. 120 random sanitized texts rendered by GitHub's markdown API showed no link outside code.
