# Design

## Decisions

- **The sources are the gh and kubectl manuals, and probes.** `gh help environment` names `GH_BROWSER`, `BROWSER`, `GH_EDITOR`, `GH_PAGER` and `GH_PATH`. The `kubectl` pages and the source name `KUBE_EDITOR` and `KUBECTL_EXTERNAL_DIFF`. A probe with gh 2.103.3 and kubectl v1.37.1 confirms each refused key (proposal, Feasibility).
- **The guard refuses seven keys by name.** The constant holds the exact names. A `GH_*` pattern would also refuse `GH_TOKEN`, `GH_HOST` and `GH_REPO`, which callers set (the session pins `GH_TOKEN` on each gh child, #767), and it would need an accepted set and a change of `_is_env_override_refused`. The names of both tools that run a program are few and documented, and the other keys of #2673 and #2674 edit the same constant, so a block of names merges without conflict.
- **`BROWSER` is refused.** It is the documented fall-back of `GH_BROWSER`, as `VISUAL`, `EDITOR` and `PAGER` are the fall-backs of the git editor and pager (#2205, #2483). No caller sets it as an override. `k8s/tunnel.py` passes the ambient value to `cloudflared` through `extra_allowed_env`, and the guard does not check that path, so the tunnel login still opens the browser of the person.
- **`GH_PATH` is refused.** gh writes its value as the path of the git credential helper, and git starts it. The probe needs two steps (`gh auth setup-git`, then a git command that asks for a credential), because the program runs in the second step. The effect lasts in the git configuration, so the guard refuses the key.
- **`GH_CONFIG_DIR` is accepted.** It is in `CONST_GH_LOGIN_ENV_VARS`, and the gh login lookup of `devcontainer.py` gives it so that gh finds the login of the person. A configuration directory can hold a `!` alias that starts a program (probe), but a caller that names the directory chooses a place that it controls. This is the case of `HOME` and `XDG_CONFIG_HOME` in #2483. A caller that takes the directory from an untrusted source must check it first.
- **`KUBECONFIG` is accepted.** It is in `DEFAULT_ALLOWED_ENV_VARS`, and `KubeApiRelay.env` of the sandbox gives the kubeconfig of the relay to its child. A kubeconfig can hold an `exec` credential plug-in (probe). The caller names a file that it controls, as for `HOME` in #2483. The relay file holds no credentials and no plug-in.
- **`XDG_DATA_HOME` is accepted.** gh runs an extension that it finds below the data directory, but only when the arguments name that extension (probe). The key names a place for files, like `XDG_CONFIG_HOME`.
- **The new names sit in a block of their own.** The block is between the ssh keys and the Python keys, with one comment for each group. The comment of the constant is not edited.
- **The spec change only adds requirements,** and the tests are in `tests/test_subprocess_env_gh_kubectl.py`, so that the work of #2673 and #2674 on the neighbouring test file and constant block merges without conflict.

## Rejected alternatives

- **Refuse all seven keys of the issue.** `GH_CONFIG_DIR` and `KUBECONFIG` are set by the callers of the code base (proposal, Feasibility), so a refusal breaks the gh login lookup and the sandbox relay.
- **Accept all seven keys.** The probes ran a program for five of them, and a refused key costs no caller.
- **Refuse `GH_*` and keep an accepted set of gh keys.** It follows the git change (#2483), but the gh keys are few and mixed with credentials, and the change would add an accepted set that no other family needs.
- **Check the value of the key.** The value is a path, and a new option or another program name passes such a check.

## Keys considered and not claimed

- `KUBECTL_PATH`: kubectl sets it for a plug-in and ignores the value in the environment (probe).
- `KUBECTL_KUBERC`: the file holds aliases and default options. No probe ran a program with it.
- `GH_TELEMETRY_ENDPOINT_URL` and `GH_DEBUG`: they name a place for data, not a program, and are outside this change.

## Non-goals

- The library keys that load a module: #2503.
- The keys that make a child write a file that the caller names: #2674.
