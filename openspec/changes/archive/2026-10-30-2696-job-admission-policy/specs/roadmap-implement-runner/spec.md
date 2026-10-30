# Spec Delta

## ADDED Requirements

### Requirement: An admission policy covers only the Jobs of the Service
A ValidatingAdmissionPolicy and a binding SHALL apply to `CREATE` and `UPDATE` of `batch/v1` `jobs` in namespace `devops`, with `failurePolicy: Fail` and the action `Deny`. A match condition SHALL limit the policy to the user `system:serviceaccount:devops:roadmap-service`, which is the subject of the RoleBinding `roadmap-service-jobs`. The expressions SHALL use only standard CEL.

#### Scenario: The scope is read
- **WHEN** a test reads the rendered policy, binding and RoleBinding
- **THEN** the rules cover `CREATE` and `UPDATE` of `jobs` only, the binding selects namespace `devops`, the failure policy is `Fail`, the action is `Deny`, and the user in the match condition equals the subject of the RoleBinding

#### Scenario: Another identity
- **WHEN** the policy is evaluated for a Job that breaks a rule, made by the CLI user, Argo CD or the CronJob controller
- **THEN** the match condition is false, so the policy does not refuse the Job

### Requirement: The policy pins the image and the account of a Job of the Service
The policy SHALL refuse a Job unless it has one container and no init container, the image of the container is `ghcr.io/dan-petty/devops-cli/runner` alone or followed by `:` or `@`, and the pod uses ServiceAccount `devops-cli` with `automountServiceAccountToken: false`.

#### Scenario: A Job with another image or account
- **WHEN** the Job from the template changes in one way: another repository, an image that only starts with the repository name, a second container, an init container, another ServiceAccount, or a token that mounts or is not set
- **THEN** the policy refuses the Job and names the rule

### Requirement: The policy pins the secrets, the volumes and the host of a Job of the Service
The policy SHALL refuse a Job unless each `envFrom` names only Secret `devops-cli`, no `env` entry has `valueFrom`, the volumes are only `tmp` and `home` (`emptyDir`) and `config` (ConfigMap `devops-cli-config`), and the pod sets no `hostNetwork`, `hostPID` or `hostIPC`.

#### Scenario: A Job with another source or volume
- **WHEN** the Job from the template changes in one way: a ConfigMap or another Secret in `envFrom`, an `env` with `valueFrom`, a `hostPath` volume, a Secret volume, a ConfigMap volume of another name, `hostNetwork`, `hostPID` or `hostIPC`
- **THEN** the policy refuses the Job and names the rule

### Requirement: The policy bounds the run of a Job of the Service
The policy SHALL refuse a Job unless it sets `backoffLimit: 0` and an `activeDeadlineSeconds` that is at most the value of CronJob `devops-cli-runner`. A Job that the Job builder makes from that CronJob SHALL pass the policy.

#### Scenario: A Job from the runner template
- **WHEN** a test builds the Job from the rendered CronJob `devops-cli-runner` with `build_job`, the environment value and the labels of the Service, and evaluates the policy for the Service user
- **THEN** the policy admits the Job, also when the image carries a tag, a digest, or both

#### Scenario: A Job that runs too long or retries
- **WHEN** the Job from the template sets a `backoffLimit` above 0, an `activeDeadlineSeconds` one above the template's, or no `activeDeadlineSeconds`
- **THEN** the policy refuses the Job
