# Tasks

## 1. The reads of the planner

Kind: behavior

- [x] 1.1 Add failing tests of `read_issue`, `find_issues` and `get_last_comments` for an item and a comment of an account with no write access, and for the two trusted bots (`tests/roadmap/stage/test_roadmap_stage_github.py`, `tests/github/test_github_client_issue_reads.py`).
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_github.py tests/github/test_github_client_issue_reads.py`
- [x] 1.2 Give `IssueView`, `OpenItem` and the comments of `get_last_comments` the relation and the login of the author, let `trust.is_trusted` and `trust.trusted_replies` take each record with an author, and apply both in `StageGitHub` (`src/devops_cli/github/client.py`, `src/devops_cli/roadmap/trust.py`, `src/devops_cli/roadmap/stage/stage_github.py`).
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_github.py tests/roadmap/stage/test_roadmap_stage_tools.py tests/github/test_github_client_issue_reads.py tests/roadmap/test_roadmap_trust.py`

## 2. The files of prepare

Kind: behavior

- [x] 2.1 Add failing tests of the issue files, the issue index, the pull request files, `pulls.json` and the issue listing for an item of an account with no write access (`tests/roadmap/stage/test_roadmap_stage_github_snapshot.py`, `tests/roadmap/stage/test_roadmap_stage_prepare.py`).
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_github_snapshot.py tests/roadmap/stage/test_roadmap_stage_prepare.py`
- [x] 2.2 Apply `trust.is_trusted` and `last_trusted_comments` in the snapshot and in `issue_listing` (`src/devops_cli/roadmap/stage/stage_github_snapshot.py`, `src/devops_cli/roadmap/stage/stage_job_phases.py`).
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_github_snapshot.py tests/roadmap/stage/test_roadmap_stage_prepare.py`

## 3. The request of the planner

Kind: behavior

- [x] 3.1 Add failing tests of the open pull requests and of `issue_dependencies` for an item of an account with no write access, for a pull request with no author, and for the author type `Bot` (`tests/roadmap/stage/test_roadmap_stage_overlap.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`).
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_overlap.py tests/roadmap/stage/test_roadmap_stage_plan.py`
- [x] 3.2 Read the author of each open pull request in the same GraphQL request and give `trust.TITLE_LEFT_OUT` in place of the title of an item of another account in the overlap list and in `issue_dependencies` (`src/devops_cli/roadmap/stage/stage_overlap.py`, `src/devops_cli/roadmap/stage/stage.py`).
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_overlap.py tests/roadmap/stage/test_roadmap_stage_plan.py tests/roadmap/stage/test_roadmap_stage_request.py`

## 4. Documents

Kind: other

- [x] 4.1 Add the section "The text of other items" to `docs/roadmap/stage.md`, and correct the rows of `read_issue` and `find_issues` and the line of `prepare`.
  - Verification: `$ uv run devops ci --check --only docs,openspec`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
