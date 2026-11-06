# Tasks

## 1. Keep the angle-bracket text of a code span

Kind: behavior. Reads: `src/devops_cli/roadmap/refine.py` (`_replace_outside_code`, `_shown_code`, `sanitize_text`). Changes: `tests/roadmap/test_roadmap_refine.py`, `src/devops_cli/roadmap/refine.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_refine.py`, add the cases of the spec. A code span and a code block with `<section>.<option>` or `<read command>` stay as they are. A tag outside code shows as text, acts as no tag and loses no word. A text with a backtick that opens no code span shows no raw tag. An end marker and a comment opener are neutralized also in a code span. The input `A tag <<b></b>!-- rebuilt` builds no comment opener.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine.py` fails on the base
- [x] 1.2 In the same file, add a property test over text made of backticks, tags, comment openers, link syntax, backslashes and block marks. The output holds no raw HTML. Fixed examples: ``<a title="`">`<b>` ``, a link label that builds a tag, a link label that builds an opener, and a text of many tags with backticks. Add the exact text for ``A `` `x` `<b>see</b>` B``, which only a code span that GitHub reads as text can explain. Add the cases of a `<` after one, two and three backslashes.
  - Verification: the same command fails on the base
- [x] 1.3 Change the three tests that assert the removal of a tag (`test_sanitize_text_markdown`, the case `A tag <<b></b>!-- rebuilt`, and `test_the_next_step_comment_holds_the_models_text_sanitized_and_one_line_for_each_point`) to the new form.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine.py` passes
- [x] 1.4 In `src/devops_cli/roadmap/refine.py`, replace `_HTML_TAG_RE` with `_HTML_TAG_OPENER_RE`. Add `_shows_stray_backtick`, `_escaped_tags`, `_escape_tag_opener` and `_without_raw_html`. Make `sanitize_text` call `_without_raw_html` after the images go and after the rewrite of the links. Compute the run length and the stray state after the first call. Update the docstring of `sanitize_text`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine.py tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_stage_apply.py tests/roadmap/test_roadmap_stage_plan.py` passes

## 2. Keep a tag as it is in a title

Kind: behavior. Reads: `src/devops_cli/roadmap/stage_change.py` (`staging_title`, `delivery_title`, `safe_text`). Changes: `tests/roadmap/test_roadmap_stage_title.py`, `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/stage_change.py`.

- [x] 2.1 In `tests/roadmap/test_roadmap_stage_title.py`, add the cases of the spec. `staging_title` and `delivery_title` keep `<section>.<option>`. A comment opener in a title becomes an entity. A summary of the most characters that the schema accepts, with a tag at its end, fits.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_title.py` fails on the base
- [x] 2.2 In `src/devops_cli/roadmap/refine.py`, give `sanitize_text` the keyword `escape_tags`. In `src/devops_cli/roadmap/stage_change.py`, add `safe_title` and use it in `staging_title`, `delivery_title` and the check of the summary.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_title.py tests/roadmap/test_roadmap_stage_content.py tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## Criteria

- Refine neutralizes the model text that GitHub hides, links or cross-references: group 1
- Refine shows no raw HTML in the model's text: group 1
- A title shows a tag as text: group 2

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
