# Tasks

## 1. Resolve a plan citation against the staged tree

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_paths.py`, `tests/roadmap/test_roadmap_stage_content.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_content.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_stage_content.py`, add a failing test that passes a dict as `read_text` to `check_proposal`: a citation of line 4 that holds other text is refused with the field and the path, a citation of the line that holds the text is accepted, a line past the end is refused, a `path:def f` citation of a file that defines `def f(` at line 7 is accepted, a `path:def f` citation of a file that defines only `def g(` is refused, a stale citation of `what_changes` names that field, a plan with no `read_text` gets no citation problem, and a citation whose spacing differs is accepted
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` fails on the base
- [x] 1.2 Add a helper in `src/devops_cli/roadmap/stage_change.py` that finds each citation of the form `path:line:text`, `path:def name` and `path:class name` in `feasibility`, `why` and each line of `what_changes`. Give `check_proposal` an optional `read_text: Callable[[str], str | None] | None = None`, default it to `None`, and call the helper with the texts of the three fields and that reader. Refuse a citation of fewer than 3 characters, and compare the cited text with the cited line as a substring after collapsing white space in both and stripping backticks and one trailing period. Refuse a citation whose path or line the reader does not return. Name the field and the cited path in each problem
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` passes

## 2. Pass a reader of the staged commit to check_proposal

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/stage_eval_gates.py`. Changes: `src/devops_cli/roadmap/stage.py`.

- [ ] 2.1 In `src/devops_cli/roadmap/stage.py`, where `_Planner` calls `check_proposal` in `_settle`, pass a `read_text` callable built from `self._source` and `self._sha` that returns the text of a cited file at the staged commit with the `git show <sha>:<path>` read (the form `refine.py` uses in `_read_git_file`), or `None` when the file is absent at that commit, so the check reads the staged commit and not the working tree
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes
- [ ] 2.2 Confirm the replay of the golden set in `src/devops_cli/roadmap/stage_eval_gates.py` and the plan-check command in `src/devops_cli/roadmap/plan_check.py` call `check_proposal` with no reader, so the default `read_text` judges no citation and the recorded plans keep passing
  - Verification: `uv run devops roadmap eval stage --replay` passes

## 3. Ask the planner for a symbol citation

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`, `docs/ROADMAP_WORKFLOW.md`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [ ] 3.1 Add a rule to the stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` that states the `path:line:text`, `path:def name` and `path:class name` citation forms, and tells the planner to cite a symbol instead of a line number when a line is not needed. Add a test in `tests/roadmap/test_roadmap_stage_prompt_rules.py` that reads the prompt and asserts the symbol form and the instruction to prefer it
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
