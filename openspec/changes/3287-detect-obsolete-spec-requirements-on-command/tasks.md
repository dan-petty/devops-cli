# Tasks

## 1. Read the statement of each base requirement

Reads: `src/devops_cli/roadmap/stage/stage_specs.py`, `openspec/specs/roadmap-intake-duplicates/spec.md`, `tests/roadmap/stage/test_roadmap_stage_specs.py`. Changes: `src/devops_cli/roadmap/stage/stage_specs.py`, `tests/roadmap/stage/test_roadmap_stage_specs.py`.

- [x] 1.1 Add to `tests/roadmap/stage/test_roadmap_stage_specs.py` a test that `read_spec` gives each requirement name with its statement, that the statement of the first requirement holds its text and no line of its scenario, and that a spec with no requirement gives an empty tuple of statements
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_specs.py` fails on the base
- [x] 1.2 Add a field `statements: tuple[tuple[str, str], ...] = ()` to `BaseSpec` in `src/devops_cli/roadmap/stage/stage_specs.py`, and fill it in `read_spec` from a helper that takes the text of each requirement from its heading to its first scenario or the next heading, on one line as `_spec_requirements` of `src/devops_cli/roadmap/plan_check.py` does. Update the docstrings of the module and of `BaseSpec`
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_specs.py` passes

## 2. Refuse a stale base requirement

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`, `tests/support/builders.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`.

- [x] 2.1 Add to `tests/roadmap/stage/test_roadmap_stage_content.py` a case that an added requirement saying `devops roadmap intake-eval` must not exist with an unmodified base requirement that names it gives one problem that names the command and the requirement, a case that the same base requirement in `modified` with text that omits the name gives no problem, a case that a modified text which keeps the name gives one problem, a case that an added requirement removing `--old` gives one problem, a case that a call with no base texts gives no problem, and a case that builds the plan's own `StageProposal` and asserts that `content_problems` returns no problem for it
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py` fails on the base
- [x] 2.2 Add the message entries `stage_problem_stale_command` and `stage_problem_stale_command_text` to the roadmap messages of `src/devops_cli/lang/en/messages.py`. Add `requirement_texts` to the keyword arguments of `check_gates` and `check_proposal`, pass it to `_delta_problems`, and add `_stale_command_problems(spec, texts)`: read each ADDED requirement whose text holds MUST NOT or SHALL NOT, take each code span that starts with `devops ` or with `--`, and return one problem for each base requirement that names it and is not in `modified`, and one for each `modified` requirement whose text keeps it. Update the docstrings of `check_gates` and `check_proposal`
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py` passes

## 3. Give the check the base requirement texts of the job

Reads: `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/support/builders.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`.

- [x] 3.1 Add to `tests/roadmap/stage/test_roadmap_stage_plan.py` a plan run whose base spec names `devops roadmap intake-eval` and whose first reply adds a requirement that removes it while leaving that base requirement unchanged, and assert that the job sends the problem back to the model, then a run whose second reply lists the base requirement in `modified` and assert that the plan is written
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py` fails on the base
- [x] 3.2 Build `self._requirement_texts = {name: dict(spec.statements) for name, spec in specs.items()}` beside `self._requirements` in the planner of `src/devops_cli/roadmap/stage/stage.py`, and pass `requirement_texts=self._requirement_texts` in the `check_proposal` call of `_settle`
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py` passes

## 4. State the rename rule in the stage prompt

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [x] 4.1 Add to `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` a test that the stage prompt holds a rule which names `modified`, a command or an option that the issue removes or renames, and each base requirement that names the old name
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` fails on the base
- [x] 4.2 Add a bullet after the spec-delta rule of `src/devops_cli/ai/tasks/roadmap_stage_change.md`: when the issue removes or renames a `devops` command or an option, each base requirement that names the old name goes into `modified` with text that omits it, and an unmodified base requirement that names it is refused. State in one task of this group that the change runs `uv run devops roadmap eval stage --replay` and gives the replay score before and after the change, with the same model for both runs
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes

## 5. List a living spec first in a references answer

Reads: `src/devops_cli/roadmap/stage/stage_references.py`, `tests/roadmap/stage/test_roadmap_stage_tools.py`. Changes: `src/devops_cli/roadmap/stage/stage_references.py`, `tests/roadmap/stage/test_roadmap_stage_tools.py`.

- [ ] 5.1 Change the expected answer of `test_references_lists_every_file_that_holds_a_name_with_its_count` in `tests/roadmap/stage/test_roadmap_stage_tools.py` so that the line of the spec file of the fixture comes before the line of its source file, and add a test that `reference_answer` lists a spec path before a source path for the same name
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_tools.py` fails on the base
- [ ] 5.2 Put `specs` first in `_GROUPS` of `src/devops_cli/roadmap/stage/stage_references.py`, and update the comment above it and the module docstring so that they say a living spec comes before the source, the tests and the documents
  - Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_tools.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
