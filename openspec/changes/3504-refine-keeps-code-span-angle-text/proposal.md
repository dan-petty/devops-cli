# Proposal

## Why

Issue #3504 reports that the sanitizer of the refine job deletes each `<word>` as an HTML tag, also inside a code span. `sanitize_text` in `src/devops_cli/roadmap/refine.py` ran `_HTML_TAG_RE` on the whole text. So a requirement or a command in a refine section lost its placeholders. `<section>.<option>` in a code span became `.`. `devops <read command> --help` became `devops  --help`. The text `use <read command> here` became `use  here`.

The issue lists the sections of ten open items with this damage. A reader of the section sees a damaged requirement. The alternatives check, the stage job and the pull request describe command call the same function, so their text had the same defect.

## What Changes

- `sanitize_text` keeps a code span and a code block as they are. Outside code, it changes the `<` of each tag into `&lt;`. So no raw tag renders and no word is lost. A tag is a `<` with a letter or a slash after it. The code does not look for the closing `>`.
- A `<` that an odd number of backslashes escapes stays as it is. GitHub shows it as text. An entity after the backslash would show as the text `&lt;`.
- The step that finds the tags outside code is `_escaped_tags`. It uses `_replace_outside_code`, the code-aware path that already finds the links and the references through the tokens of markdown-it-py.
- An escaped tag can hold a backtick that opens a code span. That span can take a later tag out of code. So `_escaped_tags` repeats while the text changes. It stops after three passes and then changes each tag, also in code. A hostile text then takes time in proportion to its length.
- In a text with a backtick that opens no code span, no span is code for a tag. The same function applies this rule to links, handles and references.
- The rewrite of a link drops the `[` and the `](` of its label. So the text around a label can build a tag or an opener. `sanitize_text` looks for tags and openers again after the rewrite. The input `<[b>](https://example.com/a)` no longer gives a raw `<b>`.
- A comment opener (`<!`, `<?`) still becomes `&lt;`, also in code. An end marker still becomes `[end-marker]`, also in code. The record block and the markers are found in the raw text (#2478).
- `_HTML_TAG_RE` goes. A tag now loses its `<` and nothing else, so the text around a tag builds no opener. The input `A tag <<b></b>!-- rebuilt` gives `A tag <&lt;b>&lt;/b>!-- rebuilt`.
- A title is plain text. GitHub shows a raw `<section>` as text and counts its characters, and the squash commit takes the title as it is. So `staging_title` and `delivery_title` use the new `safe_title`, which keeps each tag as it is. `safe_title` still turns a comment opener into an entity. `sanitize_text` gets the keyword `escape_tags` for this.
- Three tests that assert the removal of a tag change to the new form. New tests cover the cases of the issue, the titles and a property over the whole function.
- The change does not repair a section that refine already wrote.
- The change alters what a consumer observes, so it carries spec deltas on `roadmap-refine` and `roadmap-stage`. The requirement of `roadmap-alternatives` that the model's text makes no HTML tag still holds, because an escaped tag is text.
- The change fits one pull request. Issue #3500 changes the refine loop in another pull request. This change touches only `sanitize_text`, its helpers and the title functions.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine`: Refine neutralizes the model text that GitHub hides, links or cross-references
- `roadmap-stage`: A title shows a tag as text

## Impact

- Code: `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/stage_change.py`
- Tests: `tests/roadmap/test_roadmap_refine.py`, `tests/roadmap/test_roadmap_stage_title.py`
- Specs: `openspec/specs/roadmap-refine/spec.md` and `openspec/specs/roadmap-stage/spec.md` (by archive)

## Feasibility

- Command output at `origin/main` commit ed91c67c. A call of `sanitize_text(raw, set())` gives these results, as the issue says. ``The span `<section>.<option>` stays.`` gives ``The span `.` stays.``. ``Run `devops <read command> --help` now.`` gives ``Run `devops  --help` now.``. `Use <read command> here` gives `Use  here`.
- The Markdown API of GitHub (`POST /markdown`, mode `gfm`), called through `devops gh api markdown`, shows what GitHub does with each form. The raw text `Use <read command> here.` renders as `Use  here.`, so GitHub reads `<read command>` as a tag and hides its words. The text `Use &lt;read command> here.` renders as `Use <read command> here.`. A code span with `devops <read command> --help` renders with its text. The raw text `<section>.<option> end.` renders `<section>` as a real element that takes the text after it. So the entity form shows the words, and a code span needs no change.
- The same API shows how a backslash acts. `\<b>x` renders as the text `<b>x`. `\&lt;b>x` renders as the text `&lt;b>x`, so the entity after a backslash shows as text. `\\<b>x` renders a real `<b>` element. So only an odd number of backslashes escapes the `<`.
- A title is no Markdown. The page of pull request #2567 has the title `... forward to k8s.<domain> running`. It holds the title in an element of the class `markdown-title` as `k8s.&lt;domain&gt;`. So GitHub shows a raw tag word as text. The public issue `zhaofinger/finger-blog#11` has the title `&lt;script /&gt; async &amp; defer`. Its page holds `&amp;lt;script /&amp;gt;`. So an entity in a title shows as the text `&lt;`. The line of #2567 in `CHANGELOG.md` holds `k8s.&lt;domain&gt;`, so release-please escapes a tag word of a squash subject by itself. So a title must keep its tags as they are.
- markdown-it-py 4.2.0, pinned in `pyproject.toml`, gives `html_inline` and `html_block` tokens for a raw tag, and `code_inline` and `fence` tokens for code. `_shown_code` and `_replace_outside_code` already read these tokens for #2525. The tests use the same parser to check the result. So the change adds no new parse.
- A first version of the step ran one pass. A property test with a `hypothesis` search over text made of backticks, tags and block marks found the input ``<a title="`">`<b>` ``. The first pass leaves `<b>` in code. Then the escaped first tag shows a backtick that opens a new code span, which takes `<b>` out of code. So the step repeats.
- A second version repeated until the text was stable. A text of 5.6 KB made of the repeat ``<a title="`">` `` took 3.9 s, because each pass parses the whole text. After the cap of three passes it takes 0.02 s, and a text of 112 KB takes 0.25 s.
- A review found that a link rewrite builds a tag: `<[b>](https://x.y)` gave a raw `<b>`, and a label `!-- devops-roadmap-record ... --` gave a forged record block. After the second look, a search of 30,000 texts finds no raw tag. The search holds the pieces `[b>`, `[!--`, `](https://example.com/a)`, backslashes and images.
- The issue gives the line numbers `refine.py:1215`, `:1343`, `:1363` and `:1365`. They are `:1223`, `:1351`, `:1371` and `:1373` at the base commit, and the code is as the issue describes it. The tests that assert a removed tag are three, not two: `test_sanitize_text_markdown`, the case `A tag <<b></b>!-- rebuilt`, and `test_the_next_step_comment_holds_the_models_text_sanitized_and_one_line_for_each_point`.

## Existing Tool Considered

The change uses what exists: the `markdown-it-py` tokens through `_replace_outside_code`, and the entity `&lt;`, which a Markdown parser turns into the text `<`. A library that cleans HTML, for example `nh3` or `bleach`, removes a tag or an attribute, so it loses the words of `<read command>`. It works on HTML and not on Markdown text, so it cannot tell a code span from text. No new dependency and no new regex for code are necessary.

The change adds one regex of the `<` before a letter or a slash, two small functions, `_escaped_tags` and `safe_title`, and one keyword. It deletes `_HTML_TAG_RE`. The written cost is about 30,000 tokens to build, about 1,000 tokens per year to keep and fix, and about three hours elapsed.
