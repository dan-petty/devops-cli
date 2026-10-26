# Tasks

## 1. Post-Helm CRD verification on teardown and deploy

- [x] 1.1 Add failing tests in `tests/test_k8s.py` verifying that teardown-stack skips deleting post-Helm manifests and deploy-stack reports apply failures when CRDs are not served, and verify with `uv run devops ci test tests/test_k8s.py`.
- [x] 1.2 Implement CRD discovery check and skip/report logic in `src/devops_cli/commands/k8s/stack_lifecycle.py` and message templates in `src/devops_cli/lang/en/messages.py`, and verify with `uv run devops ci test tests/test_k8s.py`.
- [x] 1.3 Regenerate documentation with `uv run devops docs generate --sync-readme`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
