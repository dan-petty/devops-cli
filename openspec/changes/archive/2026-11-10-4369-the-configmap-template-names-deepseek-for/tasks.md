# Tasks

## 1. The template

- [x] 1.1 Change the tests that pinned Sonnet so that they assert DeepSeek and 256000 for `analysis` and `stage`, and see them fail on the old template
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Set `analysis` and `stage` in `k8s/devops/configmap.example.yaml`
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_configmap.py tests/config/test_k8s_devops_runtime.py tests/roadmap/stage/test_roadmap_stage_window.py`

## 2. Documents

- [x] 2.1 Update `k8s/README.md`, `docs/roadmap/stage.md` and `SECURITY.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- The ladder of the template and of the live ConfigMap differ. The follow-up is in the pull request comment.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
