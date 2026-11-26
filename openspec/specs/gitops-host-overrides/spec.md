# gitops-host-overrides Specification

## Purpose
How devops-cli treats the hosts and the environment values that Argo CD sets on the Applications of the environment tree: where the Argo CD gate permits the placeholder domain, and that `devops k8s deploy-stack` writes no override on a cluster that Argo CD manages.

## Requirements

### Requirement: The Argo CD gate permits the placeholder only in host fields
The Argo CD gate SHALL permit the placeholder domain only in the host fields of the Applications `devops`, `ingress` and `mattermost`: the hosts of an Ingress, an IngressRoute and a Mattermost, each container `env[].value` of a Deployment, and each `data` value of a ConfigMap. The infra repo sets the real values with Kustomize patches of the Application.

#### Scenario: A Deployment holds the placeholder in an env value and in an argument
- **WHEN** the Application `devops` renders a Deployment with the placeholder in an env value and in an argument
- **THEN** the gate refuses only the argument

#### Scenario: A ConfigMap holds the placeholder in a data value and in an annotation
- **WHEN** the Application `devops` renders a ConfigMap with the placeholder in a data value and in an annotation
- **THEN** the gate refuses only the annotation

### Requirement: deploy-stack writes no Application override
On a cluster that Argo CD manages, `devops k8s deploy-stack` SHALL NOT patch an Argo CD Application, and SHALL NOT need a domain.

#### Scenario: Deploy of the infra stack
- **WHEN** `deploy-stack --stack infra` runs with no domain on a cluster that Argo CD manages
- **THEN** it exits 0 and writes no object
