# Tasks

## 1. The template

- [x] 1.1 Add the tests that pin one DeepSeek tier for `edit` and `repair` and the comment above the ladder, and see them fail on the old template
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Set the two ladders and the comment in `k8s/devops/configmap.example.yaml`
  - Verification: `$ uv run devops ci test tests/config/test_k8s_devops_runtime.py tests/roadmap/implement/test_roadmap_implement_step_classes.py tests/k8s/test_k8s_configmap.py`

## 2. Documents

- [x] 2.1 Update `k8s/README.md` (item 19) and `SECURITY.md` (rule 13)
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
