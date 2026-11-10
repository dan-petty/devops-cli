# Tasks

## 1. Read the text of a citation from the span that follows it

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_citation_quote.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_citation_quote.py`, assert that a citation whose text stands in the code span after `path:line:` is accepted when the line holds it, and is refused when the line holds other text, when the text has fewer than 3 characters and when no span follows
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_citation_quote.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/stage/stage_change.py`, take the text of a line citation from the code span that follows `path:line:` when the text up to the next backtick is empty
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_citation_quote.py tests/roadmap/stage/test_roadmap_stage_content.py` passes

## 2. Keep the golden replay

- [x] 2.1 Run the replay and state that every gate refuses what it must refuse and that 5 of 5 good plans pass
  - Verification: `$ uv run devops roadmap eval stage --replay`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
