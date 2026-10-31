# Tasks

## 1. The reads of the row

- [x] 1.1 Write failing tests in `tests/github/test_pr_check_verdict.py` and `tests/github/test_github_client.py`: `read_check_runs` reads the check runs of a commit and sends no request to the commit status endpoint, a head with no check run reads as pending, a failed or cancelled run is not passing, and `get_pull_status` gives the head commit
  - Verification: `uv run devops ci test tests/github/test_pr_check_verdict.py tests/github/test_github_client.py`
- [x] 1.2 Add `read_check_runs` to `src/devops_cli/github/check_verdict.py` and `head_sha` to `PullStatus` in `src/devops_cli/github/client.py`
  - Verification: `uv run devops ci test tests/github/test_pr_check_verdict.py tests/github/test_github_client.py`

## 2. The decision and the round

- [x] 2.1 Write failing tests in `tests/roadmap/test_roadmap_stage_ready.py` for the scenarios of the requirement "The Service marks a green stage pull request ready": a green draft is marked once, a failed, a running and an absent check keep the draft, a draft of a person is never read, a second round sends no request, a pull request that left the draft state is only recorded, no recorded draft sends no request, an item with `implement.job` is left alone, one failed item does not stop the other, and no request goes to the commit status endpoint
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_ready.py`
- [x] 2.2 Add `StageRecordKey.READY`, make `write_each` of `stage.py` public, and write `src/devops_cli/roadmap/stage_ready.py` with `ready_to_mark` and `mark_stage_ready`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_ready.py tests/roadmap/test_roadmap_stage_apply.py`

## 3. The row

- [x] 3.1 Write failing tests in `tests/roadmap/test_roadmap_stage_ready.py`, `tests/roadmap/test_roadmap_run.py` and `tests/roadmap/test_roadmap_implement_submit.py`: the status lane holds `metrics`, `implement` and `stage_ready`, the new row is due on a first run and every 10 minutes, needs no clone, and the due table lists it
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_run.py tests/roadmap/test_roadmap_implement_submit.py`
- [x] 3.2 Add the row `stage_ready` and its runner to `src/devops_cli/roadmap/run.py`, `DEFAULT_ROADMAP_STAGE_READY_INTERVAL_MINUTES` to `src/devops_cli/config/defaults.py`, and the keys to `build_stub_table`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_run.py tests/roadmap/test_roadmap_implement_submit.py tests/github/test_service_limits.py`

## 4. The documents

- [x] 4.1 Replace the text that says the stage job never marks the pull request ready: the header of `src/devops_cli/roadmap/stage.py` and of `src/devops_cli/roadmap/implement.py`, the help text of `devops roadmap stage` in `src/devops_cli/lang/en/help.py`, `k8s/README.md` (Roadmap service, steps 12, 15, 17 and the new step 18), and `CONTEXT.md` (Lane)
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 5. Archive

- [ ] 5.1 Archive the change
  - Verification: `uv run devops openspec archive 2865-service-marks-stage-pr-ready`

## Workflow follow-up

- #2867 replaces the body of `ready_to_mark` with a judgement of whether the work is complete.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
