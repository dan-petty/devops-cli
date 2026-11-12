## ADDED Requirements

### Requirement: The Secret read of the sync accepts every kubeconfig context name
The Secret read of the sync SHALL check the context name with `validate_k8s_context_name`, the validator of `switch-context` and `deploy-stack`, and SHALL pass the name to `kubectl` with `--context`. An EKS ARN, a GKE name and a user-account name SHALL pass the check.

#### Scenario: An EKS ARN context
- **WHEN** the sync reads `argocd/argocd-initial-admin-secret` with the context `arn:aws:eks:us-east-1:123456789012:cluster/prod`
- **THEN** it returns the password, and `kubectl get secret` gets `--context arn:aws:eks:us-east-1:123456789012:cluster/prod`

### Requirement: The Secret read of the sync refuses an unsafe context name
The Secret read of the sync MUST refuse a context name that holds a shell metacharacter or a space, or that holds only white space, and MUST start no `kubectl` process for it.

#### Scenario: A context name with a shell metacharacter
- **WHEN** the sync reads a Secret with the context `bad; rm -rf /`
- **THEN** it exits with status 1, and it starts no `kubectl` process

### Requirement: The deploy of the infra stack syncs the credentials with an ARN context
`devops k8s deploy-stack --stack infra` SHALL exit with status 0 when the effective context is an EKS ARN, and the credential sync SHALL read the Secrets with that context.

#### Scenario: The infra stack deploys against an ARN context
- **WHEN** `devops k8s deploy-stack --stack infra --no-wait --no-push-secrets` runs with the context `arn:aws:eks:us-east-1:123456789012:cluster/prod`
- **THEN** the command exits with status 0, its output holds no `Must be a valid RFC 1123 name` message, and `kubectl get secret` gets `--context` with the ARN
