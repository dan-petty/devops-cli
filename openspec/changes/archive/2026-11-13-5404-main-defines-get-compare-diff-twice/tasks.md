# Tasks

## 1. Keep one definition

Kind: fix. Changes: `src/devops_cli/github/client.py`.

- [x] 1.1 Remove the first definition of `GitHubClient.get_compare_diff` and name both callers in the docstring of the one that stays
  - Verification: `$ test "$(git grep -c 'def get_compare_diff(' -- src/devops_cli/github/client.py | cut -d: -f2)" = 1`
  - Verification: `$ uv run devops ci --check --only lint,typecheck`
- [x] 1.2 Run the tests of the callers
  - Verification: `$ uv run devops ci test tests/github tests/commands/test_review_pr_post.py tests/roadmap/stage/test_roadmap_stage_ready.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
