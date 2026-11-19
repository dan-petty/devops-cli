# Tasks

## 1. Behavior

- [x] 1.1 Add AppProject trial and orphan ignore rule to k8s/argocd/apps/projects.yaml
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.2 Add egress rule to Gitea namespace in k8s/argocd/networkpolicy.yaml
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.3 Add safety rule checks for Argo CD git sources and AppProject trial
  - Verification: `$ uv run pytest tests/gate/k8s_checks/argocd_apps.py`
- [x] 1.4 Declare gitea.argocd_username setting and gitea.argocd_token credential
  - Verification: `$ uv run pytest tests/security/test_config_declarations.py`
- [x] 1.5 Add gate_namespace to ClusterSecret and register argocd/gitea-repo-creds
  - Verification: `$ uv run pytest tests/k8s/test_cluster_secret_plan.py tests/k8s/test_cluster_secret_push.py`
- [x] 1.6 Add branch and contents querying methods to GiteaClient
  - Verification: `$ uv run pytest tests/gitea/test_gitea_client.py`
- [x] 1.7 Implement devops argo cd trial commands (start, end, list)
  - Verification: `$ uv run pytest tests/commands/test_argo_trial.py`
- [x] 1.8 Verify trial command dry run, validation, and refusal cases
  - Verification: `$ uv run pytest tests/commands/test_argo_trial.py`

## 2. Documents

- [x] 2.1 Update k8s/README.md with Gitea Trials documentation
  - Verification: `$ uv run devops ci --check --only docs`
- [x] 2.2 Add help strings in help.py and regenerate documentation
  - Verification: `$ uv run devops docs generate && uv run devops ci --check --only docs`
