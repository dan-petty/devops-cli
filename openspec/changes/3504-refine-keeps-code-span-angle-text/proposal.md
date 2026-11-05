# Proposal

## Why

Issue #3504 reports that the sanitizer of the refine job deletes each `<word>` as an HTML tag, also inside a code span. `sanitize_text` in `src/devops_cli/roadmap/refine.py` runs `_HTML_TAG_RE` on the whole text. So a requirement or a command in a refine section loses its placeholders: `<section>.<option>` in a code span becomes `.`, `devops <read command> --help` becomes `devops  --help`, and the text `use <read command> here` becomes `use  here`. The issue lists the sections of ten open items with this damage. A reader of the section sees a damaged requirement.

The job that writes the alternatives check and the stage job call the same function, so their text has the same defect.

## What Changes

- `sanitize_text` keeps a code span and a code block as they are. Outside code, it changes the `<` of each tag into `&lt;`, so no raw tag renders and no word is lost. A tag is a `<` with a letter or a slash after it, the start of an open tag and of a close tag. No look for the closing `>` is necessary.
- The step that finds the tags outside code is `_escaped_tags`. It uses `_replace_outside_code`, the code-aware path that already finds the links and the references through the tokens of markdown-it-py. It repeats until the text shows each tag in code, because an escaped tag can hold a backtick that opens a code span, and that span can take a later tag out of code.
- In a text with a backtick that opens no code span, no span is code for a tag, so each tag there becomes text. This is the rule that the same function applies to links, handles and references.
- A comment opener (`<!`, `<?`) still becomes `&lt;` also in code, and an end marker still becomes `[end-marker]` also in code, because the record block and the markers are found in the raw text (#2478).
- `_HTML_TAG_RE` goes. The opener step no longer needs to run after a tag removal, because a tag now loses its `<` and nothing else, so the text around a tag cannot build an opener again. The input `A tag <<b></b>!-- rebuilt` gives `A tag <&lt;b>&lt;/b>!-- rebuilt`.
- Three tests that assert the removal of a tag change to the new form, and new tests cover the cases of the issue and a property over the whole function.
- The change does not repair a section that refine already wrote.
- The change alters what a consumer observes (the text of a refine section, comment and block), so it carries a spec delta on `roadmap-refine`. The requirement of `roadmap-alternatives` that the model's text makes no HTML tag still holds, because an escaped tag is text.
- The change fits one pull request. Issue #3500 changes the refine loop in another pull request, and this change touches only `sanitize_text` and its helpers.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine`: Refine neutralizes the model text that GitHub hides, links or cross-references

## Impact

- Code: `src/devops_cli/roadmap/refine.py`
- Tests: `tests/roadmap/test_roadmap_refine.py`
- Specs: `openspec/specs/roadmap-refine/spec.md` (by archive)

## Feasibility

- Command output at `origin/main` commit ed91c67c. A call of `sanitize_text(raw, set())` gives these results, as the issue says: ``The span `<section>.<option>` stays.`` gives ``The span `.` stays.``, ``Run `devops <read command> --help` now.`` gives ``Run `devops  --help` now.``, and `Use <read command> here` gives `Use  here`.
- The Markdown API of GitHub (`POST /markdown`, mode `gfm`), called through `devops gh api markdown`, shows what GitHub does with each form. The raw text `Use <read command> here.` renders as `Use  here.`, so GitHub reads `<read command>` as a tag and hides its words. The text `Use &lt;read command> here.` renders as `Use <read command> here.`. A code span with `devops <read command> --help` renders with its text. The raw text `<section>.<option> end.` renders `<section>` as a real element that takes the text after it. So the entity form shows the words, and a code span needs no change.
- markdown-it-py 4.2.0, pinned in `pyproject.toml`, gives `html_inline` and `html_block` tokens for a raw tag, and `code_inline` and `fence` tokens for code. `_shown_code` and `_replace_outside_code` already read these tokens for #2525, and the tests use the same parser to check the result. So the change adds no new parse.
- A first version of the step ran one pass. A property test with a `hypothesis` search over text made of backticks, tags and block marks found the input ``<a title="`">`<b>` ``: the first pass leaves `<b>` in code, and then the escaped first tag shows a backtick that opens a new code span, which takes `<b>` out of code. The repeat until stable fixes it. After the fix, a search of 30,000 texts finds no raw tag in the output.
- The issue gives the line numbers `refine.py:1215`, `:1343`, `:1363` and `:1365`. They are `:1223`, `:1351`, `:1371` and `:1373` at the base commit, and the code is as the issue describes it. The tests that assert a removed tag are three, not two: `test_sanitize_text_markdown`, the case `A tag <<b></b>!-- rebuilt`, and `test_the_next_step_comment_holds_the_models_text_sanitized_and_one_line_for_each_point`.

## Existing Tool Considered

The change uses what exists: the `markdown-it-py` tokens through `_replace_outside_code`, and the entity `&lt;`, which a Markdown parser turns into the text `<`. A library that cleans HTML (for example `nh3` or `bleach`) removes a tag or an attribute, so it loses the words of `<read command>`, and it works on HTML and not on Markdown text, so it cannot tell a code span from text. No new dependency and no new regex for code are necessary.

The change adds one regex of four characters, the `<` before a letter or a slash, and one small function, `_escaped_tags`. It deletes `_HTML_TAG_RE`. The written cost is about 15,000 tokens to build, about 1,000 tokens per year to keep and fix, and about two hours elapsed.
