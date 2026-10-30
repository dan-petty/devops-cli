# Tasks

## 1. The rules of the reply and the line

- [x] 1.1 Write failing tests in `tests/test_roadmap_stage_plan.py`: a group with no `changes`, a blank `test`, `implementation`, `documentation` or `verify`, and a `creates` path outside `changes` each fail `StageProposal` validation; a group with no `reads` is valid; a faked first reply with an empty `changes` goes back to the model once, with the violation named, and a valid second reply stages the item; a group renders `Reads: none. Changes: ...` with no double stop, `(new)` after a created path, and no task that starts with a comma or holds `.,`.
  - Verification: `uv run devops ci test tests/test_roadmap_stage_plan.py`
- [x] 1.2 In `src/devops_cli/roadmap/stage_change.py`, add the type `Text` and the field `creates` to `StageGroup`, require `changes`, and render the line and the tasks. In `src/devops_cli/lang/en/messages.py`, add the texts for the empty `reads` and the new mark. Update `tests/support/builders.py` so the sample group marks its new test file.
  - Verification: `uv run devops ci test tests/test_roadmap_stage_plan.py tests/test_roadmap_stage_apply.py`

## 2. The comment names the missing paths

- [x] 2.1 Write failing tests in `tests/test_roadmap_stage_apply.py`: the comment names a changed path that is no file and no group creates; it names nothing for a created path or an existing file; the item is staged in both cases.
  - Verification: `uv run devops ci test tests/test_roadmap_stage_apply.py`
- [x] 2.2 Add `missing_paths` to `src/devops_cli/roadmap/stage_change.py`, keep its result in `StagedChange`, and write the warning line in the comment in `src/devops_cli/roadmap/stage.py`.
  - Verification: `uv run devops ci test tests/test_roadmap_stage_plan.py tests/test_roadmap_stage_apply.py`

## 3. The prompt and the documentation

- [x] 3.1 Change `src/devops_cli/ai/tasks/roadmap_stage_change.md` so it says that a group names at least one file in `changes`, lists the files it needs in `reads`, lists a new file in `creates`, and gives every task a text. Regenerate the documents with `uv run devops docs generate --sync-readme`.
  - Verification: `uv run devops ci docs`

## 4. The review findings

- [x] 4.1 Write failing tests in `tests/test_roadmap_stage_plan.py`: a task text of only full stops, a path with a new line or a backtick, and a second invalid reply after one return. Use `ModelFake.checking_replies` in `tests/support/fakes/model.py` for the retry.
  - Verification: `uv run devops ci test tests/test_roadmap_stage_plan.py`
- [x] 4.2 Add the type `Sentence` and the path check to `src/devops_cli/roadmap/stage_change.py`, and pass `max_retries=1` in `src/devops_cli/roadmap/stage.py`.
  - Verification: `uv run devops ci test tests/test_roadmap_stage_plan.py tests/test_roadmap_stage_apply.py`

## 5. Archive

- [x] 5.1 Archive the change.
  - Verification: `uv run devops openspec archive 2772-stage-group-files`
