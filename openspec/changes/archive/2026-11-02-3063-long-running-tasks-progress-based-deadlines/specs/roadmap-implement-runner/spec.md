## MODIFIED Requirements

### Requirement: The Service creates Jobs through a narrow Role
ServiceAccount `roadmap-service` SHALL be the account of the Service pod. A Role in namespace `devops` SHALL allow `create`, `get`, `list` and `patch` on `jobs`, `get` on `cronjobs` named `devops-cli-runner`, `list` on `pods` and `get` on `pods/log`, and nothing else. A RoleBinding SHALL bind the Role to the account and to no other subject. The Service pod SHALL mount a projected service-account token with `expirationSeconds` 3600. The pods of Jobs SHALL keep no token.

#### Scenario: The manifests are read
- **WHEN** a test reads the rendered `k8s/devops` kustomization
- **THEN** the Role holds exactly those rules, the RoleBinding names one subject, the Deployment `roadmap-service` uses ServiceAccount `roadmap-service` with `automountServiceAccountToken: false` and a projected volume with a token of 3600 seconds, and no pod template of a CronJob mounts a token

### Requirement: The policy bounds the run of a Job of the Service
The policy SHALL refuse a Job unless it sets `backoffLimit: 0` and an `activeDeadlineSeconds` that is at most 14400, the cap of `CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS`. A Job that the Job builder makes from CronJob `devops-cli-runner` SHALL pass the policy.

#### Scenario: A Job from the runner template
- **WHEN** a test builds the Job from the rendered CronJob `devops-cli-runner` with `build_job`, the environment value and the labels of the Service, and evaluates the policy for the Service user
- **THEN** the policy admits the Job, also when the image carries a tag, a digest, or both

#### Scenario: A Job that runs too long or retries
- **WHEN** the Job from the template sets a `backoffLimit` above 0, an `activeDeadlineSeconds` above the cap, or no `activeDeadlineSeconds`
- **THEN** the policy refuses the Job

#### Scenario: A Job at the cap
- **WHEN** the Job from the template sets `activeDeadlineSeconds` to the cap
- **THEN** the policy admits the Job
