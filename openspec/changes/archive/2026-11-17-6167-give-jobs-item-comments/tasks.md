# Tasks

## 1. The comments of an item and the tool that reads them

Kind: behavior. Changes: `src/devops_cli/roadmap/item_comments.py` (new), `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/roadmap/tools.py`, `src/devops_cli/config/constants.py`, `tests/support/fakes/roadmap_store.py`.

- [x] 1.1 Add the failing tests `tests/roadmap/test_roadmap_item_comments.py` and `tests/roadmap/stores/test_roadmap_github_store_comments.py`: every trusted comment oldest first, the newest whole and the older ones in an index with no cut, the count of unlisted comments, the pages of `read_comment`, and the id and the page of a comment
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_item_comments.py tests/roadmap/stores/test_roadmap_github_store_comments.py`
- [x] 1.2 Add `held_comments`, `fit_comments`, `RequestForm`, `SectionForm` and `CommentReader` in `src/devops_cli/roadmap/item_comments.py`, the id and the page of a comment in the stores, and `read_comment` in the tool registry
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_item_comments.py tests/roadmap/stores/test_roadmap_github_store_comments.py tests/roadmap/test_roadmap_tools.py`

## 2. The comments in the first plan request

Kind: behavior. Changes: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/roadmap/stage/stage_tools.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/roadmap/stage/stage_plan_record.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_tools.md`.

- [x] 2.1 Add the failing tests in `tests/roadmap/stage/test_roadmap_stage_window.py` and `tests/roadmap/stage/test_roadmap_stage_apply.py`: the first request holds a decision of a person and a report of a job, a request of code at its caps with 41 comments stays under the limit with the headroom of #6103, and the comment of a staged item names the comment page
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_window.py tests/roadmap/stage/test_roadmap_stage_apply.py`
- [x] 2.2 Read the comments of each item in the planner, fit them into the room of the body and a share of the context, give `read_comment` to each toolset, hold the comments in the plan key, name them in the comment of a staged item, and list the read in the dry run
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_window.py tests/roadmap/stage/test_roadmap_stage_apply.py tests/roadmap/test_roadmap_tools.py`

## 3. The comments in the inputs of an implement step

Kind: behavior. Changes: `src/devops_cli/roadmap/implement/implement_comments.py` (new), `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`.

- [x] 3.1 Add the failing tests `tests/roadmap/implement/test_roadmap_implement_comments.py` and a test in `tests/roadmap/implement/test_roadmap_implement_job.py`: a decision after the plan merged and a stop of a job are in the step inputs and a comment of an account with no write access is not, comments that do not fit go to the index and fail no step, the plan time of an archived change, `read_comment`, and the comment of the run names the comment page
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_comments.py tests/roadmap/implement/test_roadmap_implement_job.py`
- [x] 3.2 Add `plan_merged_at` and `StepComments`, fit the comments into the room of the step inputs, give the agent `read_comment`, read the comments once for the run, name them in the comment of the run, and list the reads in the dry run
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_comments.py tests/roadmap/implement/test_roadmap_implement_job.py tests/roadmap/implement/test_roadmap_implement_step.py`

## 4. Documents

Kind: other. Changes: `docs/roadmap/stage.md`, `docs/roadmap/implement.md`, `docs/CLUSTER.md`.

- [x] 4.1 Describe the comments of the item, the budgets and `read_comment` in the documents of the stage and the implement jobs, and regenerate the references
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
