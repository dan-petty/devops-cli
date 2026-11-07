# Tasks

## 1. Name one chat model in the ConfigMap template

Kind: behavior. Reads: `k8s/devops/configmap.example.yaml`, `tests/k8s/test_k8s_configmap.py`. Changes: the same two files.

- [x] 1.1 Write the failing test `test_every_chat_model_slot_of_the_rendered_template_names_one_hosted_group` in `tests/k8s/test_k8s_configmap.py`. It renders the repository template, resolves `ai.model` and each task of `AITasksConfig` except `embedding` with `for_task`, and asserts that all are `deepseek-v4.1-flash-1017` and that the task `embedding` is `qwen3-embedding:0.6b`. Change the test of the retry value so that it reads `ai.max_retries` only. On the base the new test fails with `devops-background` as the model.
  - Verification: `uv run devops ci test tests/k8s/test_k8s_configmap.py`
- [x] 1.2 In `k8s/devops/configmap.example.yaml`, set `ai.model` and the tasks `verification`, `chat` and `triage` to `deepseek-v4.1-flash-1017`. Add the comment with the owner decision of 2026-11-07 and the condition that ends it. Replace the comment on `ai.max_retries`; keep the value 1.
  - Verification: `uv run devops ci test tests/k8s/test_k8s_configmap.py tests/config/test_k8s_devops_runtime.py`

## 2. Fix the documents that name the old slots

Kind: documents. Changes: `k8s/README.md`, `SECURITY.md`, `CONTEXT.md`, `src/devops_cli/roadmap/run.py` (one docstring).

- [x] 2.1 Fix each place that says the Service uses `devops-background`, `devops-triage` or `claude-sonnet-5-5`, and state the data that leaves the cluster.
  - Verification: `uv run devops ci docs`
- [x] 2.2 Check the spec and the change.
  - Verification: `uv run devops openspec check`

## Workflow follow-up

- Pending a person: apply the ConfigMap with `devops k8s deploy-stack --stack devops` and restart the Service. This change applies nothing to the cluster.
- Pending a person: decide `ai.max_retries` for the hosted group after a measure of its failures.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
