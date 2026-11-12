# Tasks

## 1. A release tag starts no Copilot Setup Steps run
kind: other

- [x] 1.1 Add a contract test that refuses each workflow whose `push` trigger has a path filter and no branch or tag filter. It fails on the base with `['copilot-setup-steps.yml']`.
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`
- [x] 1.2 Add `branches: ["**"]` to the `push` trigger of `.github/workflows/copilot-setup-steps.yml`.
  - Verification: `$ uv run devops ci actionlint`

## Workflow follow-up

- Pending a person: after the next 10 release tags, `devops gh api 'repos/dan-petty/devops-cli/actions/workflows/copilot-setup-steps.yml/runs?event=push'` lists no run with a `v<version>` tag as `head_branch` that starts after the merge.
