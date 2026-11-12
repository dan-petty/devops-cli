# Design

## Decisions

- `fetch_secret_data` calls `validate_k8s_context_name(context, "context")`. It is the context validator of `switch-context`, `deploy-stack`, `argo` and `volume`, so the sync accepts each name that the command before it accepts.
- The check stays in `fetch_secret_data`, the one place where the sync starts `kubectl get secret`. `sync_k8s_credentials` and its callers add no check of their own.
- The secret name and the namespace keep the RFC 1123 check: Kubernetes names them, and the RFC 1123 rule applies to them.

## Rejected alternatives

- Keep `validate_k8s_name` for the context: it accepts only RFC 1123 names, and that is the defect. An EKS ARN fails on `:` and `/`.
- Write a new context validator: `validate_k8s_context_name` already accepts the kubeconfig names and refuses shell metacharacters, and `tests/core/test_validation.py` tests it. A second validator duplicates it.
- Keep the `logging` stack in the context test: the `logging` stack syncs no credential, so the test does not read a Secret and does not cover the defect.
