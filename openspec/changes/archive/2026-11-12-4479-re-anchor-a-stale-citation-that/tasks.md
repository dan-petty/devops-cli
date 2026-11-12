# Tasks

## 1. A stale line citation whose text is on one other line is re-anchored (behavior)

- [x] 1.1 Write failing tests: a stale citation whose text is on one other line, or on part of one other line, gets no problem; a text on no line or on two other lines is refused; a citation whose line holds the text and a short text are not re-anchored; one log line holds the count of the plan; a check with no reader writes no count.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py`
- [x] 1.2 Add `_anchored_line` and the `_Citation` record, make `_line_citation` accept a unique match at another line, and make `_plan_citation_problems` write the count of re-anchored line citations. Change the case of `tests/roadmap/stage/test_roadmap_stage_citation_quote.py` that quotes a text of another line to a text that the file does not hold.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py tests/roadmap/stage/test_roadmap_stage_citation_quote.py tests/roadmap/stage/test_roadmap_stage_gates.py`

## 2. The stage prompt states the re-anchor (behavior)

- [x] 2.1 Make the prompt-rule test ask for the new citation sentence, then change the citation sentence of `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
- [x] 2.2 Replay the golden set on the base and on the change, and state both results in the pull request.
  - Verification: `$ uv run devops roadmap eval stage --replay`

## 3. Documents

- [x] 3.1 State the re-anchor and its log line in the gate table of `docs/roadmap/plan-recheck.md`.
  - Verification: `$ uv run devops ci docs`
