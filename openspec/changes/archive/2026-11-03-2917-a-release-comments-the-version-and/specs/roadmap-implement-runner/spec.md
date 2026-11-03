## MODIFIED Requirements

### Requirement: The Service creates Jobs through a narrow Role
ServiceAccount `roadmap-service` SHALL be the account of the Service pod. A Role in namespace `devops` SHALL allow `create`, `get`, `list` and `patch` on `jobs`; `get` on `cronjobs` named `devops-cli-runner` and on `deployments` named `roadmap-service`; `list` on `pods`; `get` on `pods/log`; and nothing else. A RoleBinding SHALL bind the Role to the account only. The Service pod SHALL mount a projected token with `expirationSeconds` 3600. The pods of Jobs SHALL keep no token.

#### Scenario: The manifests are read
- **WHEN** a test reads the rendered `k8s/devops` kustomization
- **THEN** the Role holds exactly those rules, the RoleBinding names one subject, the Deployment `roadmap-service` uses ServiceAccount `roadmap-service` with `automountServiceAccountToken: false` and a projected volume with a token of 3600 seconds, and no pod template of a CronJob mounts a token
