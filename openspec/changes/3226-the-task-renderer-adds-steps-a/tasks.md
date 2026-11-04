# Tasks

## 1. The tuicr bullet follows a source change

Reads: `src/devops_cli/roadmap/stage_change.py`, `openspec/config.yaml`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 1.1 Add a failing test to tests/roadmap/test_roadmap_stage_plan.py: a plan whose groups change only SECURITY.md renders no Pending a person: review the diff in tuicr bullet and no Workflow follow-up heading, and a plan with a group that changes src/devops_cli/roadmap/stage_change.py renders the bullet
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 1.2 In tasks_text of src/devops_cli/roadmap/stage_change.py, collect the paths of the groups and write the tuicr bullet only when one of them sits under src/. Write the Workflow follow-up section only when it holds a bullet
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 2. A document task starts with a verb

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 2.1 Add a failing test to tests/roadmap/test_roadmap_stage_plan.py: a group whose documentation text is SECURITY.md renders a task that starts with Edit and names SECURITY.md, and a group whose documentation text is Document the fix in docs/TESTING.md renders it unchanged with no Edit Document
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 2.2 In the function of src/devops_cli/roadmap/stage_change.py that builds the documentation task, give the text a verb: prepend Edit when the first word is a path, meaning it holds a slash or names a file with an extension, and keep the text when its first word is a verb
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 3. The docs step follows a command or a message change

Reads: `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 3.1 Add a failing test to tests/roadmap/test_roadmap_stage_plan.py: a documentation group that changes only SECURITY.md renders no devops docs generate --sync-readme step, and a documentation group that changes src/devops_cli/commands/pr.py renders it
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 3.2 Split stage_task_documents in src/devops_cli/lang/en/messages.py into the document work and the regeneration suffix. In src/devops_cli/roadmap/stage_change.py, add the suffix only when the group changes a path in the commands package or the lang package, and keep the document work alone for every other group
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 4. The stage prompt states the documentation rule

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [ ] 4.1 Add a failing test to tests/roadmap/test_roadmap_stage_prompt_rules.py that reads the stage prompt and asserts it states the imperative verb rule, the rule that names each document, and the rule for a step that changes no document
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` fails on the base
- [ ] 4.2 Add the rule to the documentation field of the prompt in src/devops_cli/ai/tasks/roadmap_stage_change.md: the field starts with an imperative verb, names each document, and is empty when the step changes no document
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## 5. The plan reader still finds the document work

Reads: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/plan_read.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 5.1 Derive _DOCUMENTS_MARK in src/devops_cli/roadmap/plan_read.py from the document-work template of src/devops_cli/lang/en/messages.py, so the reader separates the document work from the rest of the task. Add a test to tests/roadmap/test_roadmap_stage_plan.py that builds a proposal from a change folder whose group renders a document task and asserts the document work is present
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
