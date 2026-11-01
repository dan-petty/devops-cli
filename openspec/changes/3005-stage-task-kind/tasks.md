# Tasks

## 1. A group has a kind that the validator checks

Reads: `src/devops_cli/roadmap/stage_change.py`, `tests/support/builders.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_kind.py` (new), `tests/roadmap/test_roadmap_stage_plan.py`, `tests/support/builders.py`.

- [x] 1.1 Write the tests of the kinds in `tests/roadmap/test_roadmap_stage_kind.py`: a `test` on an `other` group, a `behavior` group with no `test`, a `behavior` group that changes no path under `src/`, and an `other` group with no `verify` and no `process` or with both, each refused with the problem text. And verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_kind.py` fails on the base
- [x] 1.2 Add `GroupKind` and the fields `kind`, `process` to `StageGroup`. Make `test`, `verify` and `documentation` nullable. Add one `model_validator` that lists every problem of the group, with the messages in `messages.py`. Give the builders a `kind`. And verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_kind.py tests/roadmap/test_roadmap_stage_plan.py` passes

## 2. A group renders the tasks of its kind

Reads: `src/devops_cli/roadmap/stage_change.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_kind.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/__snapshots__/test_roadmap_stage_plan.ambr`, `tests/invariants/test_change_folders.py`, `tests/support/builders.py`.

- [x] 2.1 Write the tests of `group_text` for each kind: the groups of the plans of #2175 (a deletion with a `git grep`) and #2162 (a report, a deletion of files, a full run of CI) render with no test task and no words "fails on the base", a `process` renders its steps, a `behavior` group keeps its failing test, and a group with no `documentation` renders no documentation task. And verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_kind.py` fails on the base
- [x] 2.2 Write `group_text` by kind and render the documentation task only when `documentation` is set. Update the snapshot. And verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_kind.py tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_stage_measure.py tests/invariants/test_change_folders.py` passes

## 3. The prompts follow the kind

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `tests/roadmap/test_roadmap_stage_kind.py`.

- [x] 3.1 Write the guard test: the stage prompt and the split prompt name each value of `GroupKind` and each field of `StageGroup`, and the implement prompt names the kinds of group. And verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_kind.py` fails on the base
- [x] 3.2 Change the three prompts to the kinds: the stage and split prompts give the fields and the rules, the implement prompt says to write the failing test first when the group has a test task, and else to run the verification. And verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_kind.py tests/roadmap/test_roadmap_implement_step.py` passes

## 4. The documents state the rule

Reads: `AGENTS.md`, `docs/TESTING.md`. Changes: `AGENTS.md`, `src/devops_cli/templates/AGENTS.md.j2`, `docs/TESTING.md`, `k8s/README.md`, `openspec/config.yaml`, `src/devops_cli/roadmap/stage.py`.

- [ ] 4.1 Change rule 4 of `AGENTS.md` and of its template, the section on tests of `docs/TESTING.md`, step 15 of `k8s/README.md`, the task rules of `openspec/config.yaml` and the docstring of `stage.py` to the rule: a test for new behavior, and a command or a repeatable process for any other change. And verify that `uv run devops ci test tests/invariants/test_agents_md_claims.py tests/invariants/test_change_folders.py` passes
- [ ] 4.2 Regenerate the documents with `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
