## REMOVED Requirements

### Requirement: The check finds each token that a pod mounts
**Reason**: The check was a helper of the test that read the manifests, and #6119 deletes that test (#6060: no test asserts a value of a manifest).
**Migration**: kube-linter (`uv run devops k8s lint`) reports a workload that mounts the token of the default ServiceAccount, and `kubectl get pods -A -o json` shows each token volume.
