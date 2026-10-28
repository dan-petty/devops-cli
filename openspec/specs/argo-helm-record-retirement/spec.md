# argo-helm-record-retirement Specification

## Purpose
Which Helm release records `devops argo cd apps retire-helm-records` deletes after Argo CD adopts a chart, which records it keeps, what it reads, and that the AppProject reports a left-over record.

## Requirements

### Requirement: Only a release that an Application renders is planned
The command SHALL plan the records of a release only when an Argo CD Application renders that release: a source of the Application has a `chart`, and the release name is that source's `helm.releaseName`, or else the Application's name, in the Application's destination namespace.

#### Scenario: A release override
- **WHEN** Application `stack` renders chart `loki` with `helm.releaseName: loki` in namespace `logging`, and release `loki` in namespace `logging` has a record
- **THEN** the plan names release `loki` with Application `stack`

### Requirement: A release qualifies only when Argo CD applied each of its objects
The command SHALL delete the records of a planned release only when each live object that has no owner reference and carries the release's annotations `meta.helm.sh/release-name` and `meta.helm.sh/release-namespace` carries the Application's tracking id or names `argocd-controller` as a field manager.

#### Scenario: Every object of the release is Argo CD's
- **WHEN** Application `grafana` renders chart `grafana` in namespace `monitoring`, release `grafana` has two records, its Deployment carries the tracking id `grafana:apps/Deployment:monitoring/grafana`, and its CustomResourceDefinition has no tracking id but names `argocd-controller` as a field manager
- **THEN** the plan deletes both records of release `grafana`

#### Scenario: An object that only Helm applied
- **WHEN** Application `prometheus-operator-crds` renders release `prometheus-operator-crds`, and one of its CustomResourceDefinitions has no tracking id and the field managers `helm` and `k3s` only
- **THEN** the plan deletes no record of that release and names that CustomResourceDefinition

#### Scenario: A copy that a controller made
- **WHEN** a ControllerRevision with an owner reference carries the annotations of release `grafana` and no tracking id
- **THEN** the release still qualifies

### Requirement: Records that nothing renders, or that an operator owns, stay
The command SHALL keep each record of a release that no Application renders, and each record that has an owner reference.

#### Scenario: An operator's record and an unrendered release
- **WHEN** release `k8s-monitoring-alloy-logs` has a record with an owner reference, and release `legacy` has a record but no Application renders it
- **THEN** the plan deletes neither record

### Requirement: The plan only reads, and reads no Secret data
Without `--confirm` the command SHALL make no write. It SHALL read the records and the objects through a `jsonpath` of metadata fields, so that no Secret `data` is printed.

#### Scenario: The plan
- **WHEN** a person runs `devops argo cd apps retire-helm-records`
- **THEN** it sends no `kubectl delete`, and no kubectl request that it sends asks for `data` or for JSON output of Secrets

### Requirement: --confirm deletes the planned records by name
With `--confirm` the command SHALL delete, for each qualifying release, exactly the records that the plan names, with one `kubectl delete secret -n <namespace> --ignore-not-found <records>` request.

#### Scenario: Confirmed retirement
- **WHEN** release `grafana` qualifies with records `sh.helm.release.v1.grafana.v49` and `sh.helm.release.v1.grafana.v50`, and release `prometheus-operator-crds` does not qualify
- **THEN** the command sends `kubectl delete secret -n monitoring --ignore-not-found sh.helm.release.v1.grafana.v49 sh.helm.release.v1.grafana.v50` and no delete for `prometheus-operator-crds`

### Requirement: The dry run makes no request
With `--dry-run` the command SHALL make no request and SHALL list the requests a run makes, in order, with a placeholder for each value that a read gives.

#### Scenario: Dry run
- **WHEN** a person runs `devops argo cd apps retire-helm-records --dry-run`
- **THEN** no process starts, and the output lists the Application read, the record read, the kind read, the object read and the delete that runs only with `--confirm`

### Requirement: The homelab AppProject reports a left-over record
AppProject `homelab` SHALL NOT ignore Secrets named `sh.helm.release.v1.*` as orphans.

#### Scenario: The AppProject
- **WHEN** `k8s/argocd/apps/projects.yaml` is read
- **THEN** no `orphanedResources.ignore` entry of AppProject `homelab` names `sh.helm.release.v1.*`

### Requirement: The knowledge base runs no Helm command against an adopted release
No knowledge base page SHALL run `helm rollback`, `helm uninstall` or `helm upgrade` against a release that an Application in `k8s/argocd/apps/` renders.

#### Scenario: A Helm example
- **WHEN** a page under `src/devops_cli/ai/knowledge_base/` has the line `helm rollback prometheus 1 -n monitoring`, and Application `prometheus` renders release `prometheus`
- **THEN** the knowledge base check fails and names the page and the release
