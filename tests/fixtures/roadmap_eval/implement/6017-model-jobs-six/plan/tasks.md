# Tasks

## 1. Behavior: the value of the cluster template

- [ ] 1.1 Write a failing test: the rendered template gives `roadmap.model_jobs` 6, and the code default is 2
  - Verification: `$ uv run devops ci test tests/config/test_roadmap_model_jobs.py`
- [ ] 1.2 Set `roadmap.model_jobs: 6` with its comment in `k8s/devops/configmap.example.yaml`
  - Verification: `$ uv run devops ci test tests/config`
