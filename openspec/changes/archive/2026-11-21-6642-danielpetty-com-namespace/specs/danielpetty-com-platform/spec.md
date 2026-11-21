## Purpose
The platform side of the site danielpetty.com on the cluster: its namespace, the Argo CD AppProject that admits only the site repository and the site namespace, and the cluster Secret of its event-stream that `devops k8s push-secrets` writes.

## ADDED Requirements

### Requirement: The site namespace enforces Pod Security restricted
The root kustomization (`k8s/namespaces.yaml`) SHALL declare namespace `danielpetty-com` with the labels `pod-security.kubernetes.io/enforce`, `pod-security.kubernetes.io/warn` and `pod-security.kubernetes.io/audit` set to `restricted`, and with the annotation `argocd.argoproj.io/sync-options: Prune=false,Delete=false`.

#### Scenario: The rendered namespace
- **WHEN** a person runs `kubectl kustomize k8s | yq 'select(.kind == "Namespace" and .metadata.name == "danielpetty-com") | .metadata'`
- **THEN** the output shows the three Pod Security labels with the value `restricted` and the annotation `argocd.argoproj.io/sync-options: Prune=false,Delete=false`

#### Scenario: The live namespace
- **WHEN** Argo CD has synced Application `base`, and a person runs `kubectl get ns danielpetty-com -L pod-security.kubernetes.io/enforce`
- **THEN** the column `ENFORCE` shows `restricted`

### Requirement: AppProject danielpetty-com admits only the site repository and namespace
AppProject `danielpetty-com` in `k8s/argocd/apps/projects.yaml` SHALL list only `https://github.com/dan-petty/danielpetty.com` in `sourceRepos`, and only namespace `danielpetty-com` of server `https://kubernetes.default.svc` in `destinations`. It SHALL set `clusterResourceWhitelist: []`, and its `namespaceResourceBlacklist` SHALL hold `Role` and `RoleBinding` of group `rbac.authorization.k8s.io`. Thus an Application of the project writes no cluster-scoped object and no RBAC object.

#### Scenario: The spec of the AppProject
- **WHEN** a person runs `yq 'select(.metadata.name == "danielpetty-com") | .spec' k8s/argocd/apps/projects.yaml`
- **THEN** the output shows one source repository, one destination, `clusterResourceWhitelist: []`, and `Role` and `RoleBinding` in `namespaceResourceBlacklist`

#### Scenario: The manifest checks pass
- **WHEN** a person runs `uv run devops ci --check --only k8s,kube-linter,domain`
- **THEN** the command exits 0

### Requirement: AppProject danielpetty-com reports each orphan but the pushed Secret
AppProject `danielpetty-com` SHALL set `orphanedResources.warn` to `true`, and its `orphanedResources.ignore` SHALL hold the entry `{group: '', kind: Secret, name: event-stream}`, because `devops k8s push-secrets` writes that Secret and no Application tracks it.

#### Scenario: The pushed Secret is no orphan
- **WHEN** Secret `event-stream` exists in namespace `danielpetty-com`, an Application of project `danielpetty-com` is synced, and a person runs `kubectl -n argocd get applications -o jsonpath='{..conditions[*].type}'`
- **THEN** no Application of project `danielpetty-com` has the condition `OrphanedResourceWarning` for Secret `event-stream`

### Requirement: The push writes the event-stream Secret of the site
The cluster Secret table SHALL hold the row `danielpetty-com/event-stream` in stack `danielpetty-com`, which restarts `deployment/event-stream`. Its key `NOTE_API_KEY` SHALL read the keyring key `danielpetty_com_note_api_key`, be required, and have the generator `token_urlsafe(32)`. Its key `GITHUB_TOKEN` SHALL read the keyring key `danielpetty_com_github_token`, be optional, and have no generator. No setting SHALL read either keyring key.

#### Scenario: A push with an empty keyring
- **WHEN** namespace `danielpetty-com` exists, the keyring holds neither key, no Secret `event-stream` exists, and the push plans the row
- **THEN** `NOTE_API_KEY` is generated as a value of 43 characters for the keyring key `danielpetty_com_note_api_key`, `GITHUB_TOKEN` is skipped, and the Secret data holds only `NOTE_API_KEY`

#### Scenario: The dry run names the keys and no value
- **WHEN** a person runs `uv run devops k8s push-secrets --stack danielpetty-com --dry-run`
- **THEN** the output names `NOTE_API_KEY` and `GITHUB_TOKEN` with placeholders, holds `kubectl rollout restart deployment/event-stream -n danielpetty-com`, holds no value, and the command makes no request

### Requirement: The site stack is a detached stack
`DETACHED_STACKS` SHALL hold `danielpetty-com`. `devops k8s deploy-stack` SHALL never deploy the stack, and SHALL push its rows wherever namespace `danielpetty-com` exists.

#### Scenario: The deploy dry run lists the Secret with its condition
- **WHEN** a person runs `devops k8s deploy-stack --stack infra` as a dry run
- **THEN** the listed Secrets hold `danielpetty-com/event-stream: NOTE_API_KEY, GITHUB_TOKEN (if namespace danielpetty-com exists)`
