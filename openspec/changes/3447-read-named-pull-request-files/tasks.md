# Tasks

## 1. Read the named pull request files

Reads: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_overlap.py`, `src/devops_cli/github/client.py`, `tests/roadmap/stage/test_roadmap_stage_verify.py`. Changes: `src/devops_cli/roadmap/stage/stage_pull_files.py` (new), `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_overlap.py`, `src/devops_cli/github/client.py`, `tests/roadmap/stage/test_roadmap_stage_pull_files.py` (new), `tests/github/test_github_client.py`.

- [x] 1.1 Write `tests/roadmap/stage/test_roadmap_stage_pull_files.py`: a case that reads the changed files of a named pull request at its merge commit from a clone, a case for an unmerged pull request, a case for a read that fails, a case for a commit that the clone cannot fetch, and a case that bounds the files
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_pull_files.py` fails on the base
- [x] 1.2 Add `src/devops_cli/roadmap/stage/stage_pull_files.py` with `named_pull_requests`, `PullRequestFiles` and `pull_request_files`. Add `merged` and `merge_commit_sha` to `PullRequest` in `src/devops_cli/github/client.py`, and add `get_pull` to the `PullReads` protocol of `src/devops_cli/roadmap/stage/stage_overlap.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_pull_files.py` passes

## 2. Give the pull request files to the pass

Reads: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_verify.py`. Changes: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_verify.py`.

- [x] 2.1 Add cases to `tests/roadmap/stage/test_roadmap_stage_verify.py`: the phrase rule of `named_pull_requests`, the `pull_requests` key of the payload, and the regression case of #3410 that quotes the literal of a #3378 file
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify.py` fails on the base
- [x] 2.2 Add the `pull_requests` field to `VerificationInput`, yield its files in `request_texts`, and add its key to `payload`. In `_Planner._input_of` of `src/devops_cli/roadmap/stage/stage.py`, read the named pull requests of the item body and the plan texts and pass them to the input
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify.py` passes

## 3. Name the pull request files in the prompt

Reads: `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `tests/roadmap/stage/test_roadmap_stage_verify.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `tests/roadmap/stage/test_roadmap_stage_verify.py`.

- [x] 3.1 Add a case to `tests/roadmap/stage/test_roadmap_stage_verify.py` that reads `src/devops_cli/ai/tasks/roadmap_stage_verify.md` and asserts that the prompt names `pull_requests`, its `commit` and its files
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify.py` fails on the base
- [x] 3.2 Name the `pull_requests` key, its merge commit and its path-to-text map in `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, and tell the model to check a claim against those files
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify.py` passes

## Criteria

- Group 1: The stage job SHALL read a pull request number only when the phrase `pull request #` or `PR #` names it.
- Group 1: The read SHALL give the changed files of a named pull request at its merge commit.
- Group 1: The read SHALL give no entry for a pull request that is not merged, or that it cannot read.
- Group 1: The read SHALL hold at most `CONST_ROADMAP_STAGE_VERIFY_MAX_FILES` files, each cut to `CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS` tokens.
- Group 2: The verification input SHALL hold the named pull request files, and a quote from one SHALL be evidence for an open finding.
- Group 3: The verification prompt SHALL name `pull_requests`, its merge commit and its path-to-text map.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
