# Proposal

## Why

The task renderer of the roadmap stage job adds two pieces of text to every plan: a tuicr review bullet that openspec/config.yaml allows only for a change that alters code, and a forced docs regeneration step for every group with a documentation text. The renderer can also write a documentation text that starts with a bare path, so the task has no verb and breaks rule 9 of AGENTS.md. Issue #3226 asks for both additions to follow the paths of the groups and for a document task to start with a verb.

## What Changes

- The renderer writes the tuicr review bullet only when at least one group changes a path under src/.
- The renderer writes the Workflow follow-up section only when it holds a bullet.
- The renderer adds the docs regeneration step only for a group that changes a path in the commands package or the lang package.
- The renderer prepends the fixed verb Edit to a documentation text whose first word is a path, so SECURITY.md and docs/ROADMAP_WORKFLOW.md read as tasks.
- The renderer keeps a documentation text whose first word is a verb, so no Edit Document appears.
- The stage prompt states that the documentation field starts with an imperative verb, names each document, and is empty when the step changes no document.
- The plan reader derives its document mark from the document-work template, so it still finds the document work of a group.
- The change carries a spec delta for roadmap-stage and roadmap-plan-check, because the rendered tasks.md is the output of the stage job.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The tuicr bullet needs a source change, An empty workflow follow-up section is omitted, The docs step needs a command or a message change, A document task starts with the Edit verb, A document task keeps its own verb, The documentation field starts with an imperative verb
- `roadmap-plan-check`: The plan reader keeps the document work of a group

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/plan_read.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The probes confirm that the renderer file of the issue is at the staging commit: "The path `src/devops_cli/roadmap/stage_change.py` is a file of the staging commit."
- The probes confirm the template file of the issue: "The path `src/devops_cli/lang/en/messages.py` is a file of the staging commit."
- The probes confirm the stage prompt and the tasks rule that the change follows: "The path `src/devops_cli/ai/tasks/roadmap_stage_change.md` is a file of the staging commit." and "The path `openspec/config.yaml` is a file of the staging commit."
- The probes confirm the document of the reported plan: "The path `SECURITY.md` is a file of the staging commit."
- The agent notes are no committed file, and the probe says so: "The path `pr3157.md` is no file of the staging commit. No commit in the history deleted or renamed it." The issue cites them as notes, so their absence is no false premise.
- The context shows the renderer code that the issue names: `src/devops_cli/roadmap/stage_change.py` holds `_task_texts`, which builds the tasks of a group from its test and its implementation, and `src/devops_cli/roadmap/plan_read.py` calls both `_task_texts` and `_DOCUMENTS_MARK`.
- The context shows the word that the Edit verb replaces: `src/devops_cli/lang/en/messages.py` is a caller of `Update`, and `tests/roadmap/test_roadmap_stage_prompt_rules.py` is a test of `Edit`.
- The line numbers of the issue moved, as the issue says, so the plan names the functions and the templates and not the lines.
- First checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py`, `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` and `uv run devops openspec check`.

## Existing Tool Considered

No open, maintained tool renders a project's own task template from the paths of a plan. The change builds the rule in `src/devops_cli/roadmap/stage_change.py` and `src/devops_cli/lang/en/messages.py`: about 2,000 tokens to build, about 500 tokens to keep and fix, and about 20 minutes elapsed. The change deletes the unconditional tuicr bullet and the unconditional regeneration suffix of `stage_task_documents`.

## Dependencies

None.
