# Tasks

## 1. Measure and cut the delivery title in UTF-16 units

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/pull_form.py`, `tests/roadmap/test_roadmap_stage_title.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_title.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_stage_title.py`, add `test_the_delivery_title_counts_an_emoji_as_two_like_the_ci_check`: `delivery_title("fix(cli): " + "\U0001f600" * 30, DECLARED)` keeps the summary unchanged and its `summary_length` is 60, while a summary of 40 emoji gives a title whose summary has at most 60 units and no lone surrogate. Add `test_the_delivery_title_keeps_a_summary_of_the_exact_bound`: a summary of exactly `SUMMARY_MAX_CHARS` ASCII characters comes back whole, and one unit over the bound is cut at the limit
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_title.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/stage_change.py`, make `delivery_title` measure the summary with `summary_length` imported from `devops_cli.roadmap.pull_form`. When the count is above `SUMMARY_MAX_CHARS`, cut the summary on a code point boundary: walk the characters and keep them while the running `summary_length` stays at or below the limit, so a character above U+FFFF is kept or dropped whole. Keep the `...` marker that the current cut adds, and keep the existing steps that drop the `!` and a scope that no label declares
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_title.py` passes

## 2. State the implement title limit in code units

Reads: `openspec/specs/roadmap-implement-job/spec.md`. Changes: `openspec/specs/roadmap-implement-job/spec.md`.

- [x] 2.1 In `openspec/specs/roadmap-implement-job/spec.md`, change the requirement `The pull request that delivers the code has the type of the issue` so its text says `at most 60 UTF-16 code units` and says that a longer summary is cut at a code point boundary with no lone surrogate. Change the scenario `A long summary` to give 80 UTF-16 code units, and add the scenarios for a summary of 60 units and for a summary of 80 units of emoji. Keep the other scenarios of that requirement
  - Verification: `uv run devops openspec check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
