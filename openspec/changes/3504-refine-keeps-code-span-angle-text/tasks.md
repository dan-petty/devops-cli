# Tasks

## 1. Keep the angle-bracket text of a code span

Kind: behavior. Reads: `src/devops_cli/roadmap/refine.py` (`_replace_outside_code`, `_shown_code`, `sanitize_text`). Changes: `tests/roadmap/test_roadmap_refine.py`, `src/devops_cli/roadmap/refine.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_refine.py`, add the cases of the spec. A code span and a code block with `<section>.<option>` or `<read command>` stay as they are. A tag outside code shows as text, acts as no tag and loses no word. A text with a backtick that opens no code span shows no raw tag. An end marker and a comment opener are neutralized also in a code span. The input `A tag <<b></b>!-- rebuilt` builds no comment opener. A property test over text made of backticks, tags, comment openers and block marks finds no raw HTML in the output, with the example ``<a title="`">`<b>` `` that one pass leaves raw. Change the three tests that assert the removal of a tag (`test_sanitize_text_markdown`, the case `A tag <<b></b>!-- rebuilt`, and `test_the_next_step_comment_holds_the_models_text_sanitized_and_one_line_for_each_point`) to the new form.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/refine.py`, replace `_HTML_TAG_RE` with `_HTML_TAG_OPENER_RE`, add `_shows_stray_backtick` and `_escaped_tags`, and make `sanitize_text` call `_escaped_tags` after the comment opener step and compute the run length and the stray state again after it. Update the docstring of `sanitize_text`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine.py tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_stage_apply.py tests/roadmap/test_roadmap_stage_plan.py` passes

## Criteria

- Refine neutralizes the model text that GitHub hides, links or cross-references: group 1
- Refine shows no raw HTML in the model's text: group 1

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
