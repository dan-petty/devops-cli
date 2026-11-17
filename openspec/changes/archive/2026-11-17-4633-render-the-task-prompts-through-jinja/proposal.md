# Proposal

## Why

Values enter prompts in four ways, and no prompt can take a repository fact: `str.format` (4 sites), chained `str.replace` (3 sites), f-string concatenation (4 sites), and constants in Python (#4633). The implement step prompt takes its three tables through a `str.replace` filling in `src/devops_cli/roadmap/implement/implement_shell_policy.py`. The project already renders packaged templates through a cached Jinja2 `SandboxedEnvironment` (`src/devops_cli/core/templating.py`), and 67 of 72 task and persona files render byte-identical through one with `StrictUndefined`.

## What Changes

- `load_task_prompt(name, **context)` renders the file as a Jinja2 template through one cached `SandboxedEnvironment` when the caller passes a context, and returns the stripped file text with its markers when the caller passes none.
- The environment uses `StrictUndefined`, `keep_trailing_newline`, no `trim_blocks`, no `lstrip_blocks` and no autoescape, so a prompt with no variables keeps the text of today.
- The implement step prompt gets its three tables through context: `implement_step.step_instructions` passes `shell_programs`, `local_commands` and `shell_refusals`, and `fill_prompt` and the three placeholders go.
- `stage_plan_record.prompt_version` hashes the raw templates and the context values, so a call with no context does not raise and a context change gives a new version.
- The change carries a delta of the `ai-task-prompts` capability: `load_task_prompt` is observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-task-prompts`: `load_task_prompt` renders a template with a context

## Impact

- Code: `src/devops_cli/ai/task_loader.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `src/devops_cli/roadmap/stage/stage_plan_record.py`
- Tests: `tests/ai/test_ai_task_loader.py`, `tests/roadmap/implement/`

## Feasibility

- The premise holds in the code at the staging commit. `load_task_prompt` in `src/devops_cli/ai/task_loader.py:16` reads the file and strips it, and holds no context.
- `fill_prompt` and the three placeholders are at `src/devops_cli/roadmap/implement/implement_shell_policy.py:263` and `:604`, and the caller is `src/devops_cli/roadmap/implement/implement_step.py:441`.
- The environment follows `template_environment()` of `src/devops_cli/core/templating.py:43`, with no loader, no trimming and autoescape off.
- `roadmap_implement_step.md` holds the three `{{ }}` markers at lines 49, 53 and 57.
- The first check is `uv run devops ci test tests/ai/test_ai_task_loader.py`, which runs the new cases.
- The second check is `uv run devops ci test tests/roadmap/implement tests/roadmap/stage`, which runs the implement and stage suites beside the change.
- The third check is `! git grep -n 'fill_prompt\|PROGRAMS_PLACEHOLDER' src`, which finds nothing.
- The fourth check is `uv run devops openspec check`, which validates the added requirements and their scenarios.

## Existing Tool Considered

Jinja2 3.1.6 is pinned in `pyproject.toml` and is the project's template engine; `src/devops_cli/core/templating.py:43` already builds a cached `SandboxedEnvironment` with `StrictUndefined`. Jinja2 covers rendering with strict missing values, but it lacks prompt-aware context validation and prompt version hashing, and it reads a GitHub `${{ }}` expression as Jinja, so the loader returns a prompt raw when no context is passed. `string.Template` has no conditional block and no strict undefined; LangChain `PromptTemplate` adds a dependency and still uses Jinja2 or f-strings. This change adds no dependency. The written cost is about 6,000 tokens and about 1 hour.

## Dependencies

#4630 (a missing prompt raises), delivered.
