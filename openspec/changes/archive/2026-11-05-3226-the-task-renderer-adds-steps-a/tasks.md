# Tasks

## 1. The tuicr bullet follows a source change

Reads: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [x] 1.1 Add a failing test to `tests/roadmap/test_roadmap_stage_plan.py`: a plan whose groups change only `SECURITY.md` renders no tuicr bullet and no `## Workflow follow-up` heading, and a plan with a group that changes `src/devops_cli/roadmap/stage_change.py` keeps the bullet
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [x] 1.2 In `_tasks_file` of `src/devops_cli/roadmap/stage_change.py`, write the tuicr bullet and the `## Workflow follow-up` heading only when a group changes a path under `src/`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 2. The docs step follows a command or a message change

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/plan_read.py`, `tests/roadmap/test_roadmap_stage_kind.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/plan_read.py`, `tests/roadmap/test_roadmap_stage_kind.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [x] 2.1 Add a failing test to `tests/roadmap/test_roadmap_stage_kind.py`: a documentation group that changes only `SECURITY.md` renders no `devops docs generate --sync-readme` step, and a documentation group that changes `src/devops_cli/commands/pr.py` renders it. Rewrite the expectation of `tests/roadmap/test_roadmap_stage_plan.py` so that a group that changes no command renders no step
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_kind.py` fails on the base
- [x] 2.2 Split `stage_task_documents` in `src/devops_cli/lang/en/messages.py` into the document work and the template `stage_task_regenerate`. In `src/devops_cli/roadmap/stage_change.py`, append the regeneration suffix only when the group changes a path under `src/devops_cli/commands/` or `src/devops_cli/lang/`. In `src/devops_cli/roadmap/plan_read.py`, derive `_DOCUMENTS_MARK` from `stage_task_regenerate`, so the reader still finds the suffix
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_kind.py tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_plan_read.py` passes
- [x] 2.3 Regenerate the documentation with `uv run devops docs generate --sync-readme`, because this group changes a path under `src/devops_cli/lang/`
  - Verification: `uv run devops ci docs` passes

## 3. A document task starts with a verb

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_plan_read.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_plan_read.py`.

- [x] 3.1 Add a failing test to `tests/roadmap/test_roadmap_stage_plan.py`: a documentation text of `SECURITY.md` renders a task that reads ``Edit `SECURITY.md` ``, a text of two code-span paths renders the verb `Edit` in front of them, and a text that starts with the verb `Document` renders unchanged with no `Edit Document`. Add a failing test to `tests/roadmap/test_roadmap_plan_read.py`: a change folder whose group renders the documentation task for `SECURITY.md` reads back with the document work ``Edit `SECURITY.md` ``
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_plan_read.py` fails on the base
- [x] 3.2 In `src/devops_cli/roadmap/stage_change.py`, prepend the verb `Edit` and write the path in a code span when the first word of a documentation text is a path, which holds `/` or ends in a dot and letters. The template is `stage_document_path` in `src/devops_cli/lang/en/messages.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_plan_read.py` passes

## 4. The stage prompt states the documentation rule

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [x] 4.1 Add a failing test to `tests/roadmap/test_roadmap_stage_prompt_rules.py` that reads the stage prompt and asserts that it states the imperative verb rule, the rule that names each document in a code span, and the `null` rule for a step that changes no document
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` fails on the base
- [x] 4.2 Write the rule into the `documentation` field of `src/devops_cli/ai/tasks/roadmap_stage_change.md`: the field starts with an imperative verb, names each document in a code span, and is `null` when the step changes no document
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## 5. The planning rules state the same two rules

Reads: `openspec/config.yaml`. Changes: `openspec/config.yaml`.

- [x] 5.1 In `openspec/config.yaml`, state that a group regenerates the documentation only when it changes a path under `src/devops_cli/commands/` or `src/devops_cli/lang/`, and that a change that alters a path under `src/` ends with the tuicr bullet
  - Verification: `uv run devops openspec check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
