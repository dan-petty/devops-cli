# Tasks

## 1. Behavior

- [x] 1.1 Write a failing test: a green stage draft with a stale payload `base.sha` sends Jev the diff of the compare of the base branch and the head commit, and the round reads no diff of the pulls endpoint
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_ready_jev.py`
- [x] 1.2 Write a failing test: the pick of the scheduled release merge reads the files of a release pull request with a stale payload `base.sha` from the compare of `main` and the head commit, sends no pulls files request, and picks the pull request
  - Verification: `$ uv run devops ci test tests/release/test_release_merge_pick.py`
- [x] 1.3 Write a test: `GitHubClient.get_compare_diff` sends one request to the three-dot compare in the diff media type
  - Verification: `$ uv run devops ci test tests/github/test_github_client.py`
- [x] 1.4 Add `GitHubClient.get_compare_diff`, give it and `get_pr_diff` one private read of a diff, give `_jev_holds` the `PullStatus` of the draft, and read the release files with `get_compare_files`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`

## 2. Documents

- [x] 2.1 Say in `RELEASE_CYCLE.md` that the file guard reads the compare of `main` and the head commit
  - Verification: `$ uv run devops ci docs`
