# Tasks

## 1. Resolve a plan citation against the staged tree

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_paths.py`, `tests/roadmap/test_roadmap_stage_content.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_content.py`.

- [ ] 1.1 In `tests/roadmap/test_roadmap_stage_content.py`, add a failing test that passes a dict as `read_text` to `check_proposal`: a citation of line 4 that holds other text is refused with the field and the path, a citation of the line that holds the text is accepted, a line past the end is refused, a `path:def f` citation of a file that defines `def f(` at line 7 is accepted, a `path:def f` citation of a file that defines only `def g(` is refused, a stale citation of `what_changes` names that field, a plan with no `read_text` gets no citation problem, and a citation whose spacing differs is accepted
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` fails on the base
- [ ] 1.2 Add a helper in `src/devops_cli/roadmap/stage_change.py` that finds each citation of the form `path:line:text`, `path:def name` and `path:class name` in `feasibility`, `why` and each line of `what_changes`. Give `check_proposal` an optional `read_text: Callable[[str], str | None] | None = None`, default it to `None`, and call the helper with the texts of the three fields and that reader. Refuse a citation of fewer than 3 characters, and compare the cited text with the cited line as a substring after collapsing white space in both and stripping backticks and one trailing period. Refuse a citation whose path or line the reader does not return. Name the field and the cited path in each problem
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` passes

## 2. Read the text of a cited file from the staged checkout

Reads: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_paths.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_paths.py`.

- [ ] 2.1 In `tests/roadmap/test_roadmap_stage_paths.py`, add a failing test that a tree built from a checkout returns the text of a tracked file at that commit, and that a tree built from a list of paths returns `None`, so the replay judges no citation
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` fails on the base
- [ ] 2.2 Add a method to `class StagedTree` in `src/devops_cli/roadmap/stage_paths.py` that returns the text of one tracked file of its checkout, and `None` when the tree holds no checkout or the path is not a tracked file; it reads the file from the checkout that `StagedTree.read` already keeps, as `callers` does. Pass that method to `check_proposal` as `read_text` in `src/devops_cli/roadmap/stage.py`, and pass `None` when the tree has no checkout, so the replay of the golden set judges nothing
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` passes

## 3. Ask the planner for a symbol citation

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`, `docs/ROADMAP_WORKFLOW.md`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [ ] 3.1 Add a rule to the stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` that states the `path:line:text`, `path:def name` and `path:class name` citation forms, and tells the planner to cite a symbol instead of a line number when a line is not needed. Add a test in `tests/roadmap/test_roadmap_stage_prompt_rules.py` that reads the prompt and asserts the symbol form and the instruction to prefer it
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
