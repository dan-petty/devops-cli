# Tasks

## 1. The Status follows the pull request

- [x] 1.1 Add failing tests: the forward-only rule for each Status, a pull request with no closing issue, an issue of another repository or a closed issue, an issue that is no item, a read that fails, `pr create` and `pr ready` calls, a failed write, and the close workflow
  - Verification: `uv run devops ci test tests/test_pr_status.py`
- [x] 1.2 Add `roadmap/pull_status.py` and call it from `pr create` and `pr ready`; add `.github/workflows/clear-status.yml`; add the messages
  - Verification: `uv run devops ci test tests/test_pr_status.py tests/test_pr_cmd.py tests/commands/test_pr.py`
- [x] 1.3 Amend ADR 0016, update the help of the two commands, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs`

## Workflow follow-up

- The labels of the closed issues #2694, #2661, #2665, #2664, #2659, #2657 and #2667 are data. After the merge, an agent runs the workflow logic once by hand with `devops gh issues edit`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
