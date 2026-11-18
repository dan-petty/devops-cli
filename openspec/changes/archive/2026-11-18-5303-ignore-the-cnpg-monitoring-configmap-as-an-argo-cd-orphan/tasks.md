# Tasks

## 1. Behavior

- [x] 1.1 Add the `cnpg-default-monitoring` ConfigMap to the `homelab` AppProject `orphanedResources.ignore` list
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.2 Lock the ignore entry, the orphan warning and the kept default queries in the Argo CD apps gate
  - Verification: `$ uv run devops ci --check --only k8s`

## 2. Documents

- [x] 2.1 Extend the `homelab-project-destinations` capability
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- Pending a person: sync the `cluster` Application and read the four Applications with `kubectl get application -n argocd llm open-webui qdrant mattermost -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.conditions}{"\n"}{end}'`.
- Pending a person: review the diff in tuicr (tuicr -r main..HEAD).
