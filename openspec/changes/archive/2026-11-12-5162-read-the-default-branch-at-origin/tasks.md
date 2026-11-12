# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests: the report reads `origin/main`, not the working tree of a checkout on an old branch; the git commands come first; a missing `refs/remotes/origin/HEAD`, a failed fetch and an export with a link out of the folder are refused; the text names the commit and the branch of the checkout
  - Verification: `$ uv run devops ci test tests/infra/test_onboard.py tests/commands/test_infra_onboard.py`
- [x] 1.2 Add the shared reader `infra/repo_tree.py`, read the onboarding in its export, print the commit, and list the git commands in the dry run
  - Verification: `$ uv run devops ci test tests/infra/test_onboard.py tests/commands/test_infra_onboard.py`
- [x] 1.3 Run the command live on dan-petty/homelab with the checkout on an old branch
  - Verification: `$ uv run devops infra onboard dan-petty/homelab`

## 2. Documents

- [x] 2.1 Update the help of the command and CONTEXT.md, and regenerate the documents
  - Verification: `$ uv run devops ci docs`
