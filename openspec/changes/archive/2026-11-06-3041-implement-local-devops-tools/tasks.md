# Tasks

## 1. List the local devops commands in the shell catalog

Reads: `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `docs/ROADMAP_WORKFLOW.md`, `tests/roadmap/test_roadmap_implement_shell_policy.py`. Changes: `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `docs/ROADMAP_WORKFLOW.md`, `tests/roadmap/test_roadmap_implement_shell_policy.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_implement_shell_policy.py`, write the cases for `LOCAL_COMMANDS`: the five commands and no `network` access, the table in the prompt and in `docs/ROADMAP_WORKFLOW.md`, the third placeholder in the prompt file, `--help` of each command, and a call of `uv run devops ai repomap` that reaches the process edge with no refusal
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_shell_policy.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/implement_shell_policy.py`, add `LocalCommand`, `LOCAL_COMMANDS`, `LOCAL_COMMANDS_PLACEHOLDER` and `local_commands_table()`, and fill the placeholder in `fill_prompt`. Add the placeholder and one sentence to `src/devops_cli/ai/tasks/roadmap_implement_step.md`, and the table to `docs/ROADMAP_WORKFLOW.md`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_shell_policy.py` passes

## Criteria

- Group 1: `LOCAL_COMMANDS` SHALL hold `ci test`, `ai repomap`, `ai ast`, `docs generate` and `openspec check`, each with an access class of `read` or `write`.
- Group 1: The prompt of the step and `docs/ROADMAP_WORKFLOW.md` SHALL hold the text of `local_commands_table()`.
- Group 1: A test SHALL fail when a command of `LOCAL_COMMANDS` is not a command of the `devops` app.
- Group 1: A call of `uv run devops ai repomap` SHALL reach the process edge and SHALL NOT count as a refusal.

## Workflow follow-up

- `kubectl` and `kube-linter` in the runner tool catalog: #3562.
- Scoped `devops review` and `devops ai rag-query` calls from the shell: #3563.
- Scoped writes and the refusal budget: #3565.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
