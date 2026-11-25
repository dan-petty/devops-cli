## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Open WebUI allows only the origins of its Ingress hosts
Open WebUI SHALL read `CORS_ALLOW_ORIGIN` from ConfigMap `llm/open-webui-origins`, through a `configMapRef` in `extraEnvFrom` of `k8s/llm/values-open-webui.yaml` that is not optional. The Application `ingress` SHALL render the ConfigMap. Its value SHALL be the HTTPS origin of each host of Ingress `llm/open-webui-ingress`, in the order of the rules, separated by `;`.

#### Scenario: The origins follow the Ingress hosts
- **WHEN** the `k8s` row of `devops ci` renders the Application `ingress`
- **THEN** `CORS_ALLOW_ORIGIN` of ConfigMap `llm/open-webui-origins` is the HTTPS origin of each host of Ingress `llm/open-webui-ingress`
- **AND** `extraEnvFrom` of `k8s/llm/values-open-webui.yaml` holds `{configMapRef: {name: open-webui-origins}}`

## REMOVED Requirements

### Requirement: deploy-stack sets the configured domain in container environment values
**Reason**: The infra repo holds the patches of each Application (#7257).
**Migration**: Edit `spec.source.kustomize.patches` of the Application file in the infra repo.

### Requirement: deploy-stack fetches an Application repository with the GitHub session credential
**Reason**: `deploy-stack` renders no Application to derive an override.
**Migration**: None.

### Requirement: deploy-stack sets the configured domain in ConfigMap data values
**Reason**: The infra repo holds the patches of each Application (#7257).
**Migration**: Edit `spec.source.kustomize.patches` of the Application file in the infra repo.

### Requirement: deploy-stack sets the configured domain in the origins of Open WebUI
**Reason**: On a cluster that Argo CD manages, the infra repo holds the patch. A deploy without Argo CD keeps its behavior, which `k8s-helm-deploy` and the tests cover.
**Migration**: Edit the patch of Application `ingress` in the infra repo.
