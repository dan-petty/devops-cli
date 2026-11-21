# Proposal: #6653

## Why
#6653: a git child of devops-cli gets its GitHub credential in three ways: `_github_pin` gives it `GH_TOKEN`, `devops infra` and `deploy-stack` add the `-c` values of `CONST_GIT_GITHUB_CREDENTIAL_CONFIG`, and since #6479 the process runner inserts the same values into each network git call (`git_credential_args`). The second and third ways exist only because `build_subprocess_env` drops the `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_<n>` and `GIT_CONFIG_VALUE_<n>` of the environment, with which the devcontainer sets the helper. The owner approved the plain git flow on 2026-11-21: git finds its helper as it does in a shell.

## What Changes
- `build_subprocess_env` gives the `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_<n>` and `GIT_CONFIG_VALUE_<n>` of the environment to each child of a person, as a shell does (`CONST_GIT_CONFIG_ENV_PATTERNS`).
- A process that acts as the GitHub App gives these keys to no child, with isolation on or off. A caller override of them stays refused.
- Delete `git_credential_args` and its two inserts in the process runner, `_command_words` in `worktree_add.py`, and the per-call credential values in `infra/repo_tree.py` (`_credential`, `_FETCH`, the `shown` option of `_git`) and `k8s/argocd_overrides.py`.
- Keep `CONST_GIT_GITHUB_CREDENTIAL_CONFIG` inside `CONST_GIT_TOKEN_CALL_CONFIG`: the network calls of the implement job set `GIT_CONFIG_NOSYSTEM=1` and need the values until #3700. Keep `PreReadOrigin`.
- The change is observable (the arguments and the environment of a git child), so the specs `subprocess-environment`, `gitops-host-overrides` and `repos-worktrees-add` get deltas.

## Capabilities
- `subprocess-environment`: add the requirement of the git configuration keys, change the requirements of the isolated child and of the local git child, and remove the requirement of the inserted `-c` values.
- `gitops-host-overrides`: the fetch of `render_at_revision` holds no credential `-c` value.
- `repos-worktrees-add`: the read of `origin` uses the helper that git is configured with.

## Impact
- In the devcontainer, each git child of a `devops` command uses the helper `gh auth git-credential` of the devcontainer, which reads the session's token.
- The runner and Service images set the same helper in `/etc/gitconfig`, so the Jobs and the Service need no `-c` value.
- A person outside the devcontainer gets the helper of their own git configuration.
- The change fits one pull request.

## Feasibility
- A probe in the devcontainer (git 2.55.0): the shell holds 9 `GIT_CONFIG_*` keys, and `git config --show-scope` shows the helper of github.com only in the scope `command`. With `GIT_CONFIG_COUNT` unset, git finds only the helper of VS Code, which needs keys that `build_subprocess_env` drops.
- `Dockerfile` sets `credential.https://github.com.helper` in the system configuration of the runner image and of the Service image.
- git-config(1): `-c` values override the `GIT_CONFIG_COUNT` values, so the empty `credential.helper=` of `CONST_GIT_TOKEN_CALL_CONFIG` still clears every helper before the trusted one.
- A new test runs `devops repos worktrees add` with real git against a loopback server that asks for Basic credentials. With the old `process.py` the server gets no credential; with the change it gets the credential of the helper that the environment configures, and git gets no `-c` value.

## Existing Tool Considered
- git's own configuration through the environment (`GIT_CONFIG_COUNT`, git-config(1)) and the system configuration of the images cover the need. devops-cli builds nothing.
- Deleted internal code: `git_credential_args` and its two inserts, `_command_words`, `_credential`, `_FETCH` and the `shown` option of `_git` in `repo_tree.py`, and the credential words of `render_at_revision`.
