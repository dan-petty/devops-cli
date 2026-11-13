# Proposal: #5294

## Why

`devops k8s deploy-stack` reads the live source of each homelab Application, fetches that repository at its revision, and renders it to find the host patches (#5294). `render_at_revision` in `src/devops_cli/k8s/argocd_overrides.py` gives `git fetch` only the SSH option. It does not give git the credential of the GitHub session. Thus the fetch fails when an Application names a private repository on github.com. The homelab migration (#5120) moves the Applications `ingress` and `mattermost` to a private repository, and `deploy-stack` must work until the override path is deleted.

## What Changes

- `render_at_revision` gives `git fetch` the `-c` values of `CONST_GIT_GITHUB_CREDENTIAL_CONFIG`, as `infra/repo_tree.py` does. The empty helper value clears the helpers of the config files for github.com. Then `gh auth git-credential` gives git the token that the process runner pins on a git child that reaches a remote.
- The values apply only to `https://github.com` URLs. A fetch from another host, or over SSH, does not change.
- `k8s/README.md` says that the fetch uses the credential of the GitHub session, and that the dry run fetches nothing.
- The change alters the behavior of a devops command, so it carries a spec delta.

The change fits one pull request.

## Capabilities

- `gitops-host-overrides`: ADDED requirement "deploy-stack fetches an Application repository with the GitHub session credential".

## Impact

- `deploy-stack` renders an Application that names a private repository on github.com. A public repository renders as before: GitHub asks for no credential, so git does not call the helper.
- The fetch already gets the session's token as GH_TOKEN, because `git_reaches_remote` is true for `fetch`. The helper is scoped to `https://github.com`, so git sends the token only to github.com.
- No manifest under `k8s/` changes. Rollback: `git revert`.

## Feasibility

- Source on `origin/main` (58795b0a0): `render_at_revision` builds the fetch with `-c core.sshCommand=ssh -o BatchMode=yes` and no other `-c` value. `CONST_GIT_NONINTERACTIVE_ENV` sets `GIT_TERMINAL_PROMPT=0`, so git cannot ask for a user name. `_github_pin` in `core/process.py` gives a git child that reaches a remote the session's token as GH_TOKEN, and `git_reaches_remote` reads past `-C` and `-c` (`CONST_GIT_VALUE_OPTIONS`).
- Command output, git 2.55.0: a script called `render_at_revision` of `origin/main` through `cluster_runtime._run_cmd`, the runner of `deploy-stack`, on `https://github.com/dan-petty/homelab` at `HEAD`. The fetch failed with `fatal: could not read Username for 'https://github.com': terminal prompts disabled`. With the fix, the fetch and the checkout passed. Only `kubectl kustomize` stopped, because that repository holds no kustomization yet. The same call on the public `https://github.com/dan-petty/devops-cli`, path `k8s/overlays/homelab/ingress`, rendered 10,920 bytes.
- The issue asks for the check "`deploy-stack --stack infra --dry-run` fetches an Application that names a private repository". That check cannot pass: the dry run lists the Applications and returns before `_homelab_host_overrides` runs, and a dry run makes no request. The direct call above replaces it. A real `deploy-stack` patches the cluster, so it is not run by hand.

## Existing Tool Considered

git and gh cover the need: `gh auth git-credential` is the credential helper of gh, and git reads it from a `-c credential.<url>.helper` value. The change adds no code of its own. It uses the constant `CONST_GIT_GITHUB_CREDENTIAL_CONFIG`, which `infra/repo_tree.py` already uses. It deletes no internal code. Plan step 15 of #5120 deletes `argocd_overrides.py` after the soak.
