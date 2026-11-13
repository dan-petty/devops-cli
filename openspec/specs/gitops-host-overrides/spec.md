# gitops-host-overrides Specification

## Purpose
Which hosts and container environment values the deploy-time overrides set on the homelab Argo CD Applications, how the overrides stay in place through a sync of the app-of-apps `cluster`, and the alert that fires when a live Ingress routes a host under the placeholder domain of git.

## Requirements

### Requirement: The app-of-apps applies the homelab Applications server-side
The Applications `devops`, `ingress` and `mattermost` in `k8s/argocd/apps/` SHALL have `ServerSideApply=true` in their `argocd.argoproj.io/sync-options` annotation, and no other Application SHALL have it. The Application `cluster` SHALL have the annotation `argocd.argoproj.io/client-side-apply-migration-manager` with the value `argocd-controller`.

#### Scenario: A test reads the Application manifests
- **WHEN** a test reads `k8s/argocd/bootstrap/bootstrap.yaml`, `k8s/argocd/bootstrap/cluster.yaml` and each Application in `k8s/argocd/apps/`
- **THEN** the Applications with `ServerSideApply=true` in their sync-options annotation are `devops`, `ingress` and `mattermost` and no other
- **AND** `cluster` names `argocd-controller` as its client-side apply migration manager

### Requirement: An Ingress that routes a placeholder host alerts
The alert rule `IngressServesPlaceholderHost` in the group `homelab-services` of `k8s/monitoring/prometheus-values.yaml` SHALL fire at severity `critical` after 5 minutes for each Ingress that has a `kube_ingress_path` series with a host under the placeholder domain `example.com`. The kube-state-metrics `includeMetrics` in `k8s/monitoring/k8s-monitoring-values.yaml` SHALL keep `kube_ingress_path`.

#### Scenario: A test reads the rule
- **WHEN** a test reads the group `homelab-services`
- **THEN** `IngressServesPlaceholderHost` has the expression `count by (namespace, ingress) (kube_ingress_path{host=~"(.+\\.)?example\\.com"}) > 0`, `for: 5m` and severity `critical`

#### Scenario: The host pattern matches the hosts of git
- **WHEN** a test reads each Ingress in a YAML file under `k8s/`
- **THEN** the host pattern of the rule matches the host of each of their rules
- **AND** it does not match `argocd.example.org`, `example.com.example.net` or `notexample.com`

#### Scenario: The series reaches Prometheus
- **WHEN** a test reads `k8s/monitoring/k8s-monitoring-values.yaml` and the kube-state-metrics capture `tests/fixtures/metrics/kube-state-metrics.yaml`
- **THEN** `kube_ingress_path` is in `clusterMetrics.kube-state-metrics.metricsTuning.includeMetrics`
- **AND** the capture gives `kube_ingress_path` the labels `host`, `ingress` and `namespace`

### Requirement: deploy-stack sets the configured domain in container environment values
For each Deployment in the render of a homelab Application, `host_patches` SHALL test and then replace each `env[].value` of a container or init container that holds the placeholder domain. It SHALL change no other value, and the Argo CD gate SHALL allow the placeholder in such a value only.

#### Scenario: A Deployment holds the placeholder in three env values
- **WHEN** `host_patches` reads a Deployment with the placeholder in an init container value, two container values, an argument and an annotation, and with a value without it
- **THEN** the patch has a `test` and a `replace` operation for each of the three env values with the placeholder, and none for the argument, the annotation or the other value

#### Scenario: The Argo CD gate reads such a Deployment
- **WHEN** the Application `devops` renders a Deployment with the placeholder in an env value and in an argument
- **THEN** the gate refuses only the argument

### Requirement: deploy-stack fetches an Application repository with the GitHub session credential
`render_at_revision` SHALL give `git fetch` the `-c` values `credential.https://github.com.helper=` and `credential.https://github.com.helper=!gh auth git-credential`, in this order and before the subcommand. The empty value clears the helpers of the config files for github.com, so `gh auth git-credential` gives git the token that the process runner pins on a git child that reaches a remote. Thus `devops k8s deploy-stack` renders an Application that names a private repository on github.com.

#### Scenario: An Application names a private repository on github.com
- **WHEN** `render_at_revision` fetches `https://github.com/example/private-repository` at `main`
- **THEN** the `-c` values of the fetch name the helpers `""` and `!gh auth git-credential` for `https://github.com`, in this order
- **AND** `git_reaches_remote` is true for the arguments of the fetch, so the process runner gives it the session's token

#### Scenario: Only the fetch gets git options
- **WHEN** `render_at_revision` renders the SSH remote `ssh://git@example.com/repository.git`
- **THEN** the fetch holds the `-c` values `core.sshCommand=ssh -o BatchMode=yes`, `credential.https://github.com.helper=` and `credential.https://github.com.helper=!gh auth git-credential`, and no other command holds `-c`
- **AND** the environment of each command holds `GIT_TERMINAL_PROMPT=0` and no other key

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
