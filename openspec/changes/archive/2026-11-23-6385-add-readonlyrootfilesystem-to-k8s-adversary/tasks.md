# Tasks

## 1. Behavior

- [x] 1.1 Set securityContext on container and pod template in kubernetes_adversary.yaml
  - Verification: `$ uv run devops scan report -s trivy-config tests/fixtures/prompt_adversaries/kubernetes_adversary.yaml`
- [x] 1.2 Add test asserting securityContext on kubernetes_adversary.yaml
  - Verification: `$ uv run pytest tests/review/test_review_prompt_adversaries.py`

## 2. Verification

- [x] 2.1 Verify full test suite and openspec checks pass
  - Verification: `$ uv run devops openspec check`
