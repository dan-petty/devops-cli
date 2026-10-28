# Proposal

## Why

Issue #2525: the review of #2507, which delivered #2478, found that `sanitize_text` in `src/devops_cli/roadmap/refine.py` does not stop all the links and cross-repository references that GitHub makes from the model's text, and that it makes new ones. Build agents take Ready items as work, and a cross-repository reference puts a backlink on the issue of another repository, which #2478 sets out to stop.

- It does not put an `owner/repo#N` reference in a code span in underscore emphasis, at the end of an italic phrase or after a slash. GitHub links each one.
- It adds backticks inside a code span that holds other text. The added backtick closes the span early, so a link, a handle or a reference that was code becomes text that GitHub links.
- It does not wrap a `www.` link after `>` or at the start of a table cell, or a URL with a scheme in capitals. GitHub links them.
- A code span that it adds can pair with a lone backtick of the model's text and leave the link outside code.
- In a text with a backtick that opens no code span, GitHub's parser takes a later code span as text when an earlier one had the same length, so a link in the model's code span, or in a code span that refine adds, becomes a link. This came out of the work on this issue.

## What Changes

- `sanitize_text` finds the code in the model's text with markdown-it-py, as CommonMark with tables, and wraps nothing in it. A link, a handle or a reference in a code span or a code block stays as it is.
- In a text that shows a backtick as text, GitHub's parser can take a later code span as text. There, `sanitize_text` also wraps a link, a handle or a reference in a code span, and each code span that it adds takes a length of its own.
- One pattern finds a URL, a `www.` link, a handle and an `owner/repo#N` reference, the leftmost first. A `www.` link has no condition on the character before it. A reference can start after `_`, `/`, `*`, `.` or a handle, and takes in what follows its number up to a space or a mark. A URL takes `ftp://` and a scheme in capitals, and ends before a backtick, `|`, a bracket, a parenthesis or a backslash.
- An added code span takes one backtick more than the longest run in the text, so it closes on its own backticks only. A space goes between a replacement and a backtick next to it, or a backslash before it.
- An allowed link that a backtick follows before the next space goes in a code span, because GitHub's autolink would take that backtick.
- Refine puts each point of a comment on one line before it sanitizes the point, so a code block that the sanitizer leaves cannot become a line of text.
- The `<` of `<!` and `<?` still becomes `&lt;` in code: the record block and the markers are found in the raw text.
- The issue body and the comment that refine writes are observable, so the change carries a spec delta. The reply schema and the prompts do not change.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine`: MODIFIED the requirement for the model text that refine neutralizes, and ADDED a requirement for the code in the model's text, which refine writes as it is.

## Impact

- Code: `src/devops_cli/roadmap/refine.py`.
- Tests: `tests/test_roadmap_refine.py`.
- Documents: none. No command, option or message changes.
- Cost: at most three markdown-it-py parses of the text for each call. A 70,000-character text takes less than 0.4 s.

## Feasibility

- On `main` at e6230dcf, `sanitize_text` returns `A _cli/cli#1_ B`, `C x/cli/cli#1 D __cli/cli#1__ E`, `>www.example.com`, `|www.example.com|` and `Read HTTPS://example.com/a` with no change, and it returns ```Run `curl `www.example.com`` here``` for ``Run `curl www.example.com` here``.
- GitHub's markdown API (`uv run devops gh api -X POST markdown -f mode=gfm`, 2026-10-28) links `cli/cli#1` in `_cli/cli#1_`, `__cli/cli#1__`, `_see cli/cli#1_` and `x/cli/cli#1`, links `www.` in `>www.example.com` and in the table cell `|www.example.org|`, links `HTTPS://example.net/a`, and links `www.example.org` in ``https://x.example/`a www.example.org` `` and ``ftp://x.example/`a www.example.com` ``, where its autolink takes the backtick that would open a code span. It shows ``` Run `curl ``www.example.com`` now` ``` as one code span, and `www.example.net` between two backticks on each side as a code span. It does not link `foo_cli/cli#1`.
- markdown-it-py 4.2.0 renders ```Run `curl `www.example.com`` here``` as `<code>curl </code>www.example.com`` here`, so a backtick added in a code span puts the link outside code.
- GitHub's markdown API links `www.example.com` in ```A `` `x` `see www.example.com` B``` and `cli/cli#1` in ````` ~> ```|> `)````https://example.com/a```` a*````cli/cli#1```` `````, where CommonMark shows them as code: cmark's `scan_to_closing_backticks` keeps the last position of each run length, and once a run found no closer, it takes an opener as text when that position is before the opener. markdown-it-py 4.2.0 shows `cli/cli#1` as code in ```` [``a ` b`` ``` cli/cli#1 ` ````, which GitHub links, because the look for the end of a link label fills its own backtick cache.
- The sanitized outputs of the new tests, and of 120 random texts of backticks, brackets, marks and links, rendered by GitHub's markdown API, show every link, handle and reference as code, and the code of the input as it was. 60,000 random texts give the same result against markdown-it-py and against a copy of cmark's backtick scan.
- The new tests fail on the base for these reasons.

## Existing Tool Considered

markdown-it-py, the CommonMark parser that `refine.py` already uses for the key questions, finds the code in the model's text. tree-sitter-markdown, a dependency that gives source positions, and cmarkgfm, the Python binding of GitHub's parser, are rejected in design.md. A Markdown sanitizer such as `bleach` or `nh3` cleans HTML, not the Markdown source that GitHub renders. markdown-it-py gives no source position for an inline token, so about 20 lines mark the start of each match with a character that the text does not hold and read back which marks the parser shows as code: a few thousand tokens to write, and nothing to keep in step with a tool. The change deletes the separate handle, bare URL, `www.` and reference patterns, `_code_span_unless_allowed` and the replacements of each: one pattern and `_neutralized` take their place.
