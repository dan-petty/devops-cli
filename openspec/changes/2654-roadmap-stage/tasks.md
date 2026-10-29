# Tasks

## 1. The selection and the settings

- [x] 1.1 Write `tests/test_roadmap_stage_selection.py` (the default filter, repeated values, an unknown family, each reason to leave an item out, the limit and `--item`), and verify that `uv run devops ci test tests/test_roadmap_stage_selection.py` fails on the base: the module `devops_cli.roadmap.stage` does not exist
- [x] 1.2 Add `StageRecordKey` in `src/devops_cli/roadmap/store.py`, the constants, defaults and the `roadmap.stage.step_tokens` setting, the messages, the exception `RoadmapStageError`, `read_remote_heads` and `issue_holder` in `src/devops_cli/git/worktree_add.py`, `body_dependencies` in `src/devops_cli/roadmap/refine.py`, and the selection in `src/devops_cli/roadmap/stage.py`, and verify that `uv run devops ci test tests/test_roadmap_stage_selection.py` passes
- [x] 1.3 Regenerate the configuration documents, and verify that `uv run devops docs generate --sync-readme` leaves no diff after a second run

## 2. The plan of one item

- [x] 2.1 Write `tests/test_roadmap_stage_plan.py` (the files of a valid change, the measure of the groups, the split, the group still over budget, the validation retry, the missing binary, the secret, the closing keyword and the failures of the model), and verify that `uv run devops ci test tests/test_roadmap_stage_plan.py` fails on the base
- [x] 2.2 Add the prompts `roadmap_stage_change.md` and `roadmap_stage_split.md`, `src/devops_cli/roadmap/stage_change.py` and `plan_stage` in `src/devops_cli/roadmap/stage.py`, and verify that `uv run devops ci test tests/test_roadmap_stage_plan.py` passes
- [x] 2.3 Regenerate the documents, and verify that `uv run devops ci docs` passes

## 3. The writes of one item

- [x] 3.1 Write `tests/test_roadmap_stage_apply.py` (the branch, the one commit by the session identity, the push, the draft, the comment, the record, the stop on a refused push, the stop of a group over budget), and verify that `uv run devops ci test tests/test_roadmap_stage_apply.py` fails on the base
- [x] 3.2 Add `create_draft_pull` and `close_pull` in `src/devops_cli/github/client.py` and `apply_stage` in `src/devops_cli/roadmap/stage.py`, and verify that `uv run devops ci test tests/test_roadmap_stage_apply.py` passes
- [x] 3.3 Regenerate the documents, and verify that `uv run devops ci docs` passes

## 4. The reconcile of staged branches

- [ ] 4.1 Write `tests/test_roadmap_stage_reconcile.py` (a closed item whose branch holds only commits of the session identity, a branch with a commit by another author, and a branch that is gone), and verify that `uv run devops ci test tests/test_roadmap_stage_reconcile.py` fails on the base
- [ ] 4.2 Add the reconcile in `src/devops_cli/roadmap/stage.py`, and verify that `uv run devops ci test tests/test_roadmap_stage_reconcile.py` passes
- [ ] 4.3 Regenerate the documents, and verify that `uv run devops ci docs` passes

## 5. The command, the dry run and the documents

- [ ] 5.1 Write `tests/test_roadmap_stage_command.py` (the options, the three modes, the exit codes and the dry run) and extend `tests/test_roadmap_dry_runs.py`, and verify that `uv run devops ci test tests/test_roadmap_stage_command.py` fails on the base
- [ ] 5.2 Add the command in `src/devops_cli/commands/roadmap.py`, `stage_requests` in `src/devops_cli/roadmap/request_plan.py`, the help texts, and the terms Staged and Step in `CONTEXT.md`, and verify that `uv run devops ci test tests/test_roadmap_stage_command.py tests/test_roadmap_dry_runs.py` passes
- [ ] 5.3 Run `devops docs generate --sync-readme`, and verify that `uv run devops ci` passes

## Workflow follow-up

- The Service row of the stage job and the pinned OpenSpec in the Service image are #2659.
- The take-over of a staged branch by `devops repos worktrees add` is #2657.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
