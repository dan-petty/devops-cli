# Tasks

## 1. Context check of the Secret read (behavior)

- [ ] 1.1 Write the failing tests: the Secret read with an EKS ARN context, the refusal of an unsafe context, and the deploy and teardown of the `infra` stack with an ARN context in place of the `logging` stand-in
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_credentials.py tests/commands/k8s/test_k8s_context.py`
- [ ] 1.2 Check the context of `fetch_secret_data` with `validate_k8s_context_name` in place of `validate_k8s_name`
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_credentials.py tests/commands/k8s/test_k8s_context.py`

## 2. Archive

- [ ] 2.1 Check that the change folders are valid
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- `devops tls enable-k8s` checks its context with the RFC 1123 validator too; #4883 fixes it.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
