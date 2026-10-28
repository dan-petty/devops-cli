# Tasks

## 1. Refine wraps nothing in the model's code, and wraps each link that GitHub makes

- [x] 1.1 Write `test_sanitize_text_writes_the_code_in_the_models_text_as_it_is`, `test_sanitize_text_puts_a_link_next_to_code_in_a_code_span_of_its_own`, the property `test_sanitized_text_shows_links_handles_and_references_only_as_code`, `test_sanitize_text_neutralizes_a_comment_opener_in_a_code_span_too`, `test_a_link_in_a_code_block_of_the_models_point_is_a_code_span_on_the_points_line` and the cases of `test_sanitize_text_neutralizes_what_github_hides_links_or_cross_references` for emphasis, a slash, `>`, a table cell, a scheme in capitals, a handle, an unclosed `[` and a backtick that opens no code span in `tests/test_roadmap_refine.py`, and verify that `uv run devops ci test tests/test_roadmap_refine.py -k "sanitize or sanitized"` fails on the base
- [x] 1.2 Replace the handle, URL, `www.` and reference patterns of `sanitize_text` and `_code_span_unless_allowed` with one pattern and `_neutralized`, find the code with markdown-it-py in `_replace_outside_code`, size the added code span by the longest backtick run, give each added code span a length of its own and wrap in code spans too in a text that shows a backtick as text, put a space between a replacement and a backtick next to it in `_spaced`, and join each point of a comment on one line before it is sanitized, in `src/devops_cli/roadmap/refine.py`; verify that `uv run devops ci test tests/test_roadmap_refine.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
