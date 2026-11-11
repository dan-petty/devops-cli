# Tasks

## 1. Behavior: the loader raises for a name that is not a prompt

- [x] 1.1 Add the failing tests: a prompt of the folder loads stripped, and `missing.md` and `../personas/devsecops/role.md` raise `TaskPromptNotFoundError` that names the prompt
  - Verification: `$ uv run devops ci test tests/ai/test_ai_task_loader.py`
- [x] 1.2 Add `TaskPromptNotFoundError` to `src/devops_cli/exceptions/ai.py`, raise it from `load_task_prompt`, and delete the fallback prompts of `ai/research/socratic.py` and `ai/research/mental_model.py`
  - Verification: `$ uv run devops ci test tests/ai/test_ai_task_loader.py tests/ai/research`

## 2. Other: delete the orphan prompts and guard the folder

- [x] 2.1 Add the checks of the `test-tree` row in `tests/gate/tree_checks/task_prompts.py`: each literal or constant name given to `load_task_prompt` exists, and each file of `ai/tasks/` is named by a string literal of `src/`. Add the tests of their logic on a small tree, and delete the literal-only test of `tests/ai/test_ai_task_loader.py`
  - Verification: `$ uv run devops ci test tests/invariants/test_task_prompts_check.py`
- [x] 2.2 Delete the nine orphan files of `ai/tasks/` and the folder `ai/prompts/`, and remove the `ai/prompts/**/*.md` glob from `CONST_DOCS_CLASS_PROMPT` and from `tests/invariants/test_agents_md.py`
  - Verification: `$ uv run devops ci --only test-tree`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
