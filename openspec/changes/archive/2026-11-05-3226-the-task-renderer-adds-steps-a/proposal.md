# Proposal

## Why

Issue #3226 reports that the task renderer of the roadmap stage job adds text that a plan does not need. Every plan gets the tuicr review bullet, even a plan that changes no code. Every group with a documentation text gets the step that runs `devops docs generate --sync-readme`, even when no command, option or message changes. A documentation text that starts with a path reaches the task with no verb, which breaks rule 9 of AGENTS.md.

## What Changes

- The renderer writes the tuicr review bullet only when a group changes a path under `src/`.
- The renderer writes the `## Workflow follow-up` heading only when it holds a bullet.
- The renderer adds the step `uv run devops docs generate --sync-readme` only to a group that changes a path under `src/devops_cli/commands/` or `src/devops_cli/lang/`.
- The renderer prepends the fixed verb `Edit` to a documentation text whose first word is a path, and writes that path in a code span.
- The renderer keeps a documentation text whose first word is not a path.
- The stage prompt states the verb rule, the naming rule and the null rule of the `documentation` field.
- The plan reader derives its document mark from the template of the regeneration step, so it still finds the document work of a group.
- `openspec/config.yaml` states the same two rules as the renderer.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: the tuicr bullet needs a source change, an empty workflow follow-up section is omitted, a document task starts with the Edit verb, a document task keeps its own verb, the documentation field starts with an imperative verb, and the docs step needs a command or a message change (a modified requirement).
- `roadmap-plan-check`: the plan reader keeps the document work of a group.

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/plan_read.py`.
- Prompt: `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- Planning rules: `openspec/config.yaml`.
- Tests: `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_kind.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/test_roadmap_plan_read.py`.

## Dependencies

None. No other active change modifies the requirement that this change modifies.

## Feasibility

- The premise holds at `origin/main` commit d254410c. `git show origin/main:src/devops_cli/roadmap/stage_change.py` shows that `_tasks_file` writes the line `## Workflow follow-up` and the tuicr bullet in every call, with no test of the paths of the groups.
- The same file shows that `_task_texts` appends the documents task to every group whose `documentation` is set, and passes `REGENERATE_DOCUMENTS` to it, with no test of the paths of the group.
- `git show origin/main:src/devops_cli/lang/en/messages.py` shows the template `stage_task_documents` as `"{work}, and run `{command}`` followed by the verification line, so the step is part of every documents task.
- The issue cites line numbers that moved. The tasks function is at line 817 and the template is at line 3397 at d254410c. The check that the change needs is `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py`, and it fails on the base for the documents-only plan.
- `src/devops_cli/roadmap/stage_form.py` refuses a documentation text of one word. It does not test for a verb or a path, so a text of two words that starts with a path reaches the task.
- The first checks against the real system are `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py`, `uv run devops ci test tests/roadmap/test_roadmap_stage_kind.py` and `uv run devops openspec check`.

## Existing Tool Considered

No open, maintained tool renders the task template of this project's own plan from the paths of the plan. The change edits the renderer in `src/devops_cli/roadmap/stage_change.py` and the template in `src/devops_cli/lang/en/messages.py`. The written cost is about 2,000 tokens to build, about 500 tokens to keep and fix, and about 20 minutes of elapsed time. The change removes the unconditional tuicr bullet and the unconditional `## Workflow follow-up` heading from `_tasks_file`, and it removes the unconditional regeneration suffix from the documents task.
