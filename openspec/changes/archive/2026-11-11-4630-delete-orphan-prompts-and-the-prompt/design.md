# Design

## Decisions

- `TaskPromptNotFoundError` is a new class in `src/devops_cli/exceptions/ai.py`, a direct subclass of `DevOpsCLIError`. A missing prompt is a defect of the package, not of the user's configuration, so `ConfigurationError` does not fit. The message names the prompt, and the details hold it as `name`.
- A name that resolves outside `ai/tasks/`, such as `../personas/devsecops/role.md`, raises the same error. The loader reads only its folder, so that name is not a prompt of the loader.
- The two checks are in the `test-tree` row, which parses each file of `src/` once. `docs/TESTING.md` puts a check of committed files in a row of `devops ci`, not in a pytest test.
- The check of loaded names resolves the first argument of each call of `load_task_prompt`: a string literal, or a name bound to a string constant at the top level of its module, also through a chain of `from` imports. A parameter or a local variable, such as `task` in `refine.py` and `stage.py`, is not resolved, and the check skips it. The check fails when it resolves no name at all, so a change of the loader's name cannot make it pass with nothing to check.
- The orphan check counts a file as read when any string literal of `src/` is its file name. The prompts are named as literals, such as the persona loader's `_TASKS_DIR / "review.md"` and the table of `ai/benchmark/tasks.py`, which do not pass through `load_task_prompt`. A literal match is the one rule that covers every reader.
- The pytest test keeps only the behavior of the loader: a prompt of the folder loads stripped, and a missing name and a name outside the folder raise.

## Rejected alternatives

- `FileNotFoundError` from the loader: rejected. `CONTRIBUTING.md` asks for a typed error under `src/devops_cli/exceptions/` and refuses a bare built-in error.
- Import each module and read the constant with `getattr`: rejected. The `test-tree` row already holds the syntax tree of each module, and an import of every module that loads a prompt runs its top-level code, which loads prompts and models, so it is slow.
- A check that only reads string literals that end in `.md`: rejected. `src/` holds literals such as `tasks.md`, `proposal.md` and `spec.md` that name OpenSpec files and not prompts, so the check would report false misses.
- Keep the `ai/prompts/**/*.md` glob for a later prompt folder: rejected. The folder is empty after this change, and a glob that matches no file states a class of documents that does not exist.
