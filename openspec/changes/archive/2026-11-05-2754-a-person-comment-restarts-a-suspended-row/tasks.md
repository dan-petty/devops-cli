# Tasks

## 1. A comment of a person starts a suspended job again

Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/roadmap/trust.py`, `tests/github/test_service_limits.py`. Changes: `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/github_store.py`, `src/devops_cli/roadmap/memory_store.py`, `src/devops_cli/roadmap/trust.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_suspended_row_comment.py`, `tests/roadmap/test_roadmap_github_store.py`, `tests/roadmap/test_roadmap_store_contract.py`.

- [x] 1.1 Add `tests/roadmap/test_roadmap_suspended_row_comment.py` with a test for each scenario of four requirements. Those requirements are "A comment of a person starts a suspended job again" and "Only a person with write access is a person". The other two are "A round reads at most one page of comments" and "A round reads comments only for a job that failed". Add to `tests/roadmap/test_roadmap_github_store.py` a test for each scenario of the requirement "The store lists the comments of the repository newest first". Add to `tests/roadmap/test_roadmap_store_contract.py` a test that the in-memory store lists its comments in the same order
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_suspended_row_comment.py tests/roadmap/test_roadmap_github_store.py tests/roadmap/test_roadmap_store_contract.py` fails on the base
- [x] 1.2 Add `comments_since` to the store protocol, to `GitHubRoadmapStore` and to `InMemoryRoadmapStore`. Add `on_pull_request` to `IssueComment`. Add `is_person_comment` to `src/devops_cli/roadmap/trust.py`, which refuses a comment on a pull request. In `src/devops_cli/roadmap/run.py`, add `FailureLedger.holds_failure` and the optional comment time of `_round_input`. Add there the read of the newest 100 comments, in a round that only polls, before the rows run. Name a comment of a person in `job_suspended` of `src/devops_cli/lang/en/messages.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_suspended_row_comment.py tests/roadmap/test_roadmap_github_store.py tests/roadmap/test_roadmap_store_contract.py tests/github/test_service_limits.py`
- [x] 1.3 Run `uv run ruff check`, `uv run ruff format --check` and `uv run mypy` on the changed files
  - Verification: `uv run ruff check src/devops_cli/roadmap src/devops_cli/lang tests/roadmap/test_roadmap_suspended_row_comment.py tests/roadmap/test_roadmap_github_store.py tests/roadmap/test_roadmap_store_contract.py`

## 2. Documentation

Reads: `k8s/README.md`. Changes: `k8s/README.md`.

- [x] 2.1 Say in step 11 of the Roadmap service setup in `k8s/README.md`, in sentences of at most 25 words, four things. A comment of a person with write access on an issue is new input for a suspended job. The read is one request for each lane in a round that only polls and holds a failed job. The limit of one page bounds the read. The requests count under the row `other`. Run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
