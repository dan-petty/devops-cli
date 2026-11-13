## ADDED Requirements

### Requirement: deploy-stack sets the configured domain in ConfigMap data values
For each ConfigMap in the render of a homelab Application, `host_patches` SHALL test and then replace each `data` value that holds the placeholder domain. It SHALL change no other field of the ConfigMap, and the Argo CD gate SHALL allow the placeholder in such a value and refuse it in each other field of the ConfigMap.

#### Scenario: A ConfigMap holds the placeholder in a data value
- **WHEN** `host_patches` reads a ConfigMap with the placeholder in a data value, in an annotation and in binary data, and with a data value without it
- **THEN** the patch targets the ConfigMap with the core group `""` and version `v1`
- **AND** it has a `test` and a `replace` operation for the data value with the placeholder, and none for the annotation, the binary data or the other value

#### Scenario: The Argo CD gate reads such a ConfigMap
- **WHEN** the Application `devops` renders a ConfigMap with the placeholder in a data value and in an annotation
- **THEN** the gate refuses only the annotation

### Requirement: Open WebUI allows only the origins of its Ingress hosts
Open WebUI SHALL read `CORS_ALLOW_ORIGIN` from ConfigMap `llm/open-webui-origins`, through a `configMapRef` in `extraEnvFrom` of `k8s/llm/values-open-webui.yaml` that is not optional. The Application `ingress` SHALL render the ConfigMap. Its value SHALL be the HTTPS origin of each host of Ingress `llm/open-webui-ingress`, in the order of the rules, separated by `;`.

#### Scenario: The origins follow the Ingress hosts
- **WHEN** the `k8s` row of `devops ci` renders the Application `ingress`, before and after the patches of `host_patches` for the domain `example.org`
- **THEN** `CORS_ALLOW_ORIGIN` of ConfigMap `llm/open-webui-origins` is the HTTPS origin of each host of Ingress `llm/open-webui-ingress` in each render
- **AND** each host after the patches is under `example.org`
- **AND** `extraEnvFrom` of `k8s/llm/values-open-webui.yaml` holds `{configMapRef: {name: open-webui-origins}}`

### Requirement: deploy-stack sets the configured domain in the origins of Open WebUI
`devops k8s deploy-stack` SHALL set the configured domain in the origins of Open WebUI. On a cluster that Argo CD manages, it SHALL write them as a patch on the Application `ingress`. Without Argo CD, the stack `llm` SHALL apply the ConfigMap under the configured domain before its Helm releases.

#### Scenario: deploy-stack sets the origins on a cluster that Argo CD manages
- **WHEN** `deploy-stack --stack infra --domain example.org` runs on a cluster that Argo CD manages, and the Application `ingress` renders the ConfigMap with `https://chat.example.com`
- **THEN** the patch of the Application `ingress` tests `/data/CORS_ALLOW_ORIGIN` for `https://chat.example.com` and replaces it with `https://chat.example.org`

#### Scenario: deploy-stack applies the origins without Argo CD
- **WHEN** `deploy-stack --stack llm --domain example.org` runs on a cluster without Argo CD
- **THEN** it applies ConfigMap `llm/open-webui-origins` with `https://chat.example.org;https://homelab.example.org` before it installs the release `open-webui`
