# Tasks

## 1. The admission policy

- [x] Add the dev dependency `cel-expr-python` and failing tests in `tests/test_k8s_job_admission_policy.py`: the Job from the template is admitted in its image forms, a Job that breaks one rule is refused, another identity is not matched, and the scope, the failure policy, the action and the user are read from the rendered manifests
  - Verification: `uv run devops ci test tests/test_k8s_job_admission_policy.py`
- [x] Add `k8s/devops/roadmap-service/admissionpolicy.yaml` (the policy and its binding), list it in the kustomization of `roadmap-service` and in the manifests of `deploy-stack`
  - Verification: `uv run devops ci test tests/test_k8s_job_admission_policy.py tests/test_k8s_runner.py tests/test_k8s_roadmap_service.py tests/test_k8s_devops_stack.py`

## 2. The review fixes

- [x] Pin the pod label, refuse `priorityClassName`, `nodeName`, `imagePullSecrets`, `command` and `manualSelector`, and bound `completions` and `parallelism`, with failing tests first
  - Verification: `uv run devops ci test tests/test_k8s_job_admission_policy.py`

## 3. The documentation

- [x] Describe the policy, its guarantees and what it does not guarantee in `k8s/README.md` (Runner Jobs, the Role line, the file tree, the follow-up line), and regenerate the documents
  - Verification: `uv run devops docs generate --sync-readme .`
