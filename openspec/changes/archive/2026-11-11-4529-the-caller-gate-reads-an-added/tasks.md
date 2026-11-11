# Tasks

## 1. Read an added parameter span

Reads: `src/devops_cli/roadmap/stage/stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`. Changes: `src/devops_cli/roadmap/stage/stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_paths.py`, put the text Add `probes` to `check_proposal` back in `test_a_plan_that_leaves_out_a_caller_is_refused`. Add to the table of `test_the_caller_check_reads_only_a_parameter_that_a_task_adds` a name span, a typed span with a default, a typed span to two functions and a span after `the`, which read the function, and a decorator span, an option span and a span with other words, which read none. Write `test_a_field_of_a_model_has_no_caller_problem`. The new true cases fail on the base, which reads no function from them
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/stage/stage_paths.py`, add `_is_parameter_span`, which reads one code span with `ast` as the parameters of a `def` and refuses a name in capitals, and make `changed_functions` read a clause whose added part says parameter, argument or keyword or passes `_is_parameter_span`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py` passes

## 2. State the rule

Reads: `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [x] 2.1 State the parameter span rule of the caller check in `docs/ROADMAP_WORKFLOW.md`. Run `uv run devops roadmap eval stage --replay` on the base commit and on the change, and state both outputs and the counts of the caller reads in a pull request comment
  - Verification: `$ uv run devops ci docs`
