# Tasks

## 1. Stage leaves out an item whose plan is on the default branch

- [x] 1.1 Add failing tests: the read of `origin/<default>` with one `ls-tree`, a plan on the default branch with the branch gone, with the branch still on `origin`, with another slug, in the archive, for a closed issue, for two items, and a tree that cannot be read; the dry-run requests of stage
  - Verification: `uv run devops ci test tests/test_roadmap_planned.py tests/test_roadmap_stage_selection.py tests/test_roadmap_dry_runs.py`
- [x] 1.2 Add `roadmap/planned.py` and the directory grammars of `config/constants.py`; make `plan_stage` read the plans once and `select_stageable` leave out a planned or archived item; add the messages and the stage requests of the dry run
  - Verification: `uv run devops ci test tests/test_roadmap_planned.py tests/test_roadmap_stage_selection.py tests/test_roadmap_dry_runs.py`
- [x] 1.3 Document the new reasons in the module text of `stage.py`, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs`

## 2. The staging pull request has the type docs(openspec)

- [x] 2.1 Add failing tests: the title and the commit subject of a staging pull request for a bug and for a feature, a long summary, the branch type, and a reply with no `scope`
  - Verification: `uv run devops ci test tests/test_roadmap_stage_title.py tests/test_roadmap_stage_plan.py tests/test_roadmap_stage_apply.py`
- [x] 2.2 Add `staging_title` to `stage_change.py`; delete the `scope` of the reply and of the prompt; ask for a summary of at most 40 characters
  - Verification: `uv run devops ci test tests/test_roadmap_stage_title.py tests/test_roadmap_stage_plan.py tests/test_roadmap_stage_apply.py tests/test_ai_task_loader.py`
- [x] 2.3 Run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs`

## 3. Implement takes a Planned item

- [x] 3.1 Add failing tests: the selection of a Planned item and of a Staged item with the plan on the default branch, each reason to leave a Planned item out, the record pair, `implement.branch`, the dry-run requests, and the Service round for a Planned item
  - Verification: `uv run devops ci test tests/test_roadmap_implement_planned.py tests/test_roadmap_implement_selection.py tests/test_roadmap_implement_records.py tests/test_roadmap_implement_submit.py tests/test_roadmap_dry_runs.py tests/test_github_client.py`
- [x] 3.2 Add the Planned route to `roadmap/implement.py`, `ImplementRecordKey.BRANCH`, and `GitHubClient.update_pull` in place of `update_pull_body`
  - Verification: `uv run devops ci test tests/test_roadmap_implement_planned.py tests/test_roadmap_implement_selection.py tests/test_roadmap_implement_records.py tests/test_roadmap_implement_submit.py tests/test_roadmap_dry_runs.py tests/test_github_client.py`
- [x] 3.3 Add failing tests of the run: a Planned item with two groups to a ready pull request, a group that is done, a stop before the first commit, a stop after a commit and its retry, a draft that GitHub refuses, the fix step of a Planned item, and the delivery title of a Staged item
  - Verification: `uv run devops ci test tests/test_roadmap_implement_planned_run.py tests/test_roadmap_implement_job.py`
- [x] 3.4 Add `delivery_title` to `stage_change.py`, and the new branch, `_publish` and the title to `roadmap/implement_run.py`
  - Verification: `uv run devops ci test tests/test_roadmap_implement_planned_run.py tests/test_roadmap_implement_job.py tests/test_roadmap_implement_checks.py`
- [x] 3.5 Run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs`

## 4. The documents

- [x] 4.1 Add the term "Planned" to `CONTEXT.md`, and say in `k8s/README.md` and `docs/ROUTINE_TASKS.md` that the stage job leaves out a planned item and the implement job takes it
  - Verification: `uv run devops ci docs`
- [x] 4.2 Regenerate the documents
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops ci docs`

## 5. Archive

- [ ] 5.1 Archive the change
  - Verification: `uv run devops openspec archive 2714-planned-items`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
