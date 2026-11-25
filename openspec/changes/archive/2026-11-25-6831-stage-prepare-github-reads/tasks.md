# Tasks

## 1. GitHub client snapshot readers

Kind: behavior
Changes: `src/devops_cli/github/client.py`, `tests/github/test_github_client.py`

- [x] 1.1 Write failing tests for `GitHubClient.get_pull_files` (with `PullRequestFilePatch`) and `GitHubClient.list_open_issues` in `tests/github/test_github_client.py`.
  - Verification: `$ uv run devops ci test tests/github/test_github_client.py`
- [x] 1.2 Add `PullRequestFilePatch`, `GitHubClient.get_pull_files`, and `GitHubClient.list_open_issues` to `src/devops_cli/github/client.py` while leaving `PullRequestFile` unchanged.
  - Verification: `$ uv run devops ci test tests/github/test_github_client.py`

## 2. Stage prepare GitHub snapshot and Coder prompt

Kind: behavior
Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/stage/stage_github_snapshot.py` (new), `src/devops_cli/roadmap/stage/stage_job_phases.py`, `src/devops_cli/ai/tasks/roadmap_stage_coder.md`, `tests/roadmap/stage/test_roadmap_stage_github_snapshot.py` (new), `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/stage/test_roadmap_stage_prepare.py`, `tests/roadmap/stage/test_roadmap_stage_agent_phase.py`, `tests/roadmap/stage/test_roadmap_stage_publish.py`, `tests/roadmap/stage/test_roadmap_stage_publish_checks.py`, `tests/roadmap/stage/test_roadmap_stage_job_entry.py`, `tests/roadmap/test_roadmap_limit_classes.py`

- [x] 2.1 Write failing tests in `tests/roadmap/stage/test_roadmap_stage_github_snapshot.py` and `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` covering named issues, open PR paths, named PR file patches, 3000-issue index capping, shell `grep` search, failed-read recording in `work/github/errors.json`, stock Coder tools, unchanged `--phase all`, and prompt snapshot paths.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_github_snapshot.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
- [x] 2.2 Add snapshot constants to `src/devops_cli/config/constants.py`, register them in `tests/roadmap/test_roadmap_limit_classes.py`, implement `write_github_snapshot` in `src/devops_cli/roadmap/stage/stage_github_snapshot.py`, invoke it in `_Prepare.hand_on` (`src/devops_cli/roadmap/stage/stage_job_phases.py`) with `"github"` in `_request`, update `src/devops_cli/ai/tasks/roadmap_stage_coder.md`, and update GraphQL/fake fixtures in `tests/roadmap/stage/test_roadmap_stage_prepare.py`, `tests/roadmap/stage/test_roadmap_stage_agent_phase.py`, and `tests/roadmap/stage/test_roadmap_stage_publish.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_github_snapshot.py tests/roadmap/stage/test_roadmap_stage_prepare.py tests/roadmap/stage/test_roadmap_stage_agent_phase.py tests/roadmap/stage/test_roadmap_stage_publish.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py tests/roadmap/test_roadmap_limit_classes.py`

## 3. Documents

Kind: other
Changes: `docs/roadmap/stage.md`

- [x] 3.1 Update `docs/roadmap/stage.md` so the `--phase prepare` section names the `work/github/` snapshot files.
  - Verification: `$ uv run devops ci docs`

Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
