# Tasks

## 1. Behavior: the event-stream Secret of the site and the detached stack

- [x] 1.1 Add the failing tests. In `tests/k8s/test_cluster_secret_plan.py`: the table test lists the two entries of `danielpetty-com/event-stream`; with namespace `danielpetty-com`, an empty keyring and no live Secret, `plan_push` of `danielpetty-com/event-stream` gives `NOTE_API_KEY` the state `generated` with a value of 43 characters and the store key `danielpetty_com_note_api_key`, and `GITHUB_TOKEN` the state `skipped`; the row is in stack `danielpetty-com`, which `DETACHED_STACKS` holds, and restarts `deployment/event-stream`; `push-secrets --stack danielpetty-com --dry-run` names both keys with placeholders and the restart, and makes no request. In `tests/commands/k8s/test_k8s.py`: the `deploy-stack --stack infra` dry run lists `danielpetty-com/event-stream: NOTE_API_KEY, GITHUB_TOKEN (if namespace danielpetty-com exists)`. In `tests/invariants/test_k8s_manifests.py`: the keyring-only keys hold `danielpetty_com_note_api_key` and `danielpetty_com_github_token`
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py tests/commands/k8s/test_k8s.py tests/invariants/test_k8s_manifests.py`
- [x] 1.2 In `src/devops_cli/k8s/cluster_secrets.py`, add `danielpetty-com` to `DETACHED_STACKS`, add the keyring-only keys `DANIELPETTY_COM_NOTE_KEY` and `DANIELPETTY_COM_GITHUB_TOKEN_KEY`, and add the row `danielpetty-com/event-stream`; in `src/devops_cli/lang/en/help.py`, name `danielpetty-com` in the help of `push-secrets --stack`; regenerate the documentation with `uv run devops docs generate`
  - Verification: `$ uv run devops ci test tests/k8s/test_cluster_secret_plan.py tests/commands/k8s/test_k8s.py tests/invariants/test_k8s_manifests.py tests/k8s/test_cluster_secret_push.py tests/commands/k8s/test_k8s_gitea.py`

## 2. Manifests: the namespace, the AppProjects and the monitoring egress

- [x] 2.1 In `k8s/namespaces.yaml`, add namespace `danielpetty-com` with Pod Security `restricted` and `Prune=false,Delete=false`; in `k8s/argocd/apps/projects.yaml`, add AppProject `danielpetty-com` and the orphan ignore entry `repo-danielpetty-com` of project `homelab`; in `k8s/monitoring/networkpolicy.yaml`, add egress to namespace `danielpetty-com` on TCP 9090
  - Verification: `$ uv run devops ci --check --only k8s,kube-linter,domain`

## 3. Documents

- [x] 3.1 In `k8s/README.md`, add the two rows of `danielpetty-com/event-stream` to the Cluster Secrets table, a note on the rows of the detached stack `danielpetty-com`, and the repository Secret `repo-danielpetty-com` to the GitOps section; in `src/devops_cli/config/defaults.py`, say in the comment of `DEFAULT_ROADMAP_PROJECT_REVIEW_NAMESPACES` that namespace `danielpetty-com` holds the workloads of another project and is not in the list
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #6644 adds the Argo CD Application of the site after a person pushes the Secret.
- #6645 adds the Pixelfed namespace to the destinations of AppProject `danielpetty-com`.
- Pending a person: after the merge and the sync of Application `base`, run `kubectl get ns danielpetty-com -L pod-security.kubernetes.io/enforce` and check that it shows `restricted`.
- Pending a person: after the sync of Application `base`, push the Secret with `uv run devops k8s push-secrets --stack danielpetty-com --plan`, then `uv run devops k8s push-secrets --stack danielpetty-com`, add dan-petty/danielpetty.com to the installation of the GitHub App `devops-cli-argocd`, and create the repository Secret `repo-danielpetty-com` in namespace `argocd`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
