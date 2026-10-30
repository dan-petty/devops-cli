# Proposal

## Why

Issue #2672: the subprocess environment guard accepts the gh and kubectl keys that make a child run a program.

- `build_subprocess_env` in `src/devops_cli/core/process.py` refuses a caller override that `CONST_CODE_LOADING_ENV_PATTERNS` matches. The patterns hold no key of `gh` or `kubectl`. #2633 found the same gap for the `SSH_` keys and did not claim these keys, because no probe of them ran.
- `GH_BROWSER` names the program that `gh browse` starts. `GH_EDITOR` and `GH_PAGER` name the editor and the pager that `gh` starts. `KUBE_EDITOR` names the editor of `kubectl edit`. `KUBECTL_EXTERNAL_DIFF` names the program of `kubectl diff`.
- `BROWSER` is the fall-back of `GH_BROWSER`, as `EDITOR` and `PAGER` are the fall-backs of the editor and the pager. `GH_PATH` is the path that `gh auth setup-git` writes as the git credential helper, and git then starts it.
- `GH_CONFIG_DIR` and `KUBECONFIG` name a file or a directory that holds a program (an alias that starts with `!`, an `exec` credential plug-in). Callers set both on purpose, so the guard cannot refuse them.

## What Changes

- The guard refuses `GH_BROWSER`, `BROWSER`, `GH_EDITOR`, `GH_PAGER`, `GH_PATH`, `KUBE_EDITOR` and `KUBECTL_EXTERNAL_DIFF` as a caller override. Each raises the same `SecurityError` as the other refused keys, with isolation on and off.
- The guard keeps accepting `GH_CONFIG_DIR`, `KUBECONFIG`, `XDG_DATA_HOME` and the gh keys that name no program. The design gives the reason for each.
- `ARCHITECTURE.md` names the new refused keys. The refusal is what a consumer sees, so the change adds requirements to the `subprocess-environment` spec.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `subprocess-environment`: the guard refuses the keys of gh and kubectl that name a program. The change adds requirements and rewrites no existing requirement.

## Impact

- Code: `src/devops_cli/config/constants.py` (one new block of `CONST_CODE_LOADING_ENV_PATTERNS`).
- Tests: `tests/test_subprocess_env_gh_kubectl.py`.
- Documents: `ARCHITECTURE.md`.

## Feasibility

The guard accepts the keys today. On `origin/main` at `a3453463`, `build_subprocess_env(env={"GH_BROWSER": "x"})` returns the key with no `SecurityError`, for each key of the list above.

Each probe ran with gh 2.103.3 and kubectl v1.37.1 on Linux. It used `env -i`, a temporary `HOME`, `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring`, a fake token and a marker program that prints `MARKER-RAN` and exits 1. Only loopback addresses were used, and no probe sent a token to a real host.

- `GH_BROWSER`: `gh browse -R example/example` printed `MARKER-RAN`. The proxy was a closed local port.
- `BROWSER`: the same command with `BROWSER` printed `MARKER-RAN`. With neither key, gh looked for `xdg-open` and the other default programs.
- `GH_PAGER`: `gh help reference` with `GH_FORCE_TTY=80` printed `MARKER-RAN`.
- `GH_EDITOR`: `gh issue comment 1 --editor` in a pseudo-terminal printed `MARKER-RAN` after the key `e`. The server was a throwaway HTTPS server on the loopback address with a self-signed certificate (`SSL_CERT_FILE`), stopped after the probe.
- `GH_PATH`: `gh auth setup-git --hostname github.com --force` wrote `helper = !<marker> auth git-credential` to the git configuration of the temporary home. `git credential fill` then printed `MARKER-RAN`.
- `KUBE_EDITOR`: `kubectl edit cm x` printed `MARKER-RAN` and `there was a problem with the editor`. The API server was a throwaway HTTP server on the loopback address, stopped after the probe.
- `KUBECTL_EXTERNAL_DIFF`: `kubectl diff -f cm.yaml` against the same server printed `MARKER-RAN`. Without the key, kubectl ran `diff -u -N`.
- Accepted keys: `GH_CONFIG_DIR` with an alias `x: "!<marker>"` and `gh x` printed `MARKER-RAN`. `KUBECONFIG` with an `exec` credential plug-in and `kubectl get ns` printed `MARKER-RAN` (with an `http://` server address, kubectl started no plug-in, so the probe used `https://`). `XDG_DATA_HOME` with an installed extension `gh-x` and `gh x` printed `MARKER-RAN`.
- Keys that the probes ruled out: `KUBECTL_PATH` is set by kubectl for its plug-ins, and an own value in the environment did not reach a plug-in. A `KUBECTL_KUBERC` file holds aliases and default options, and no probe ran a program with it.
- The callers: no file of `src/` or `tests/` gives one of the seven refused keys as a caller override. `src/devops_cli/k8s/tunnel.py` names `BROWSER` in `extra_allowed_env`, which passes the ambient value to `cloudflared` and is not a caller override. `src/devops_cli/sandbox/kube_api.py` gives `KUBECONFIG`, and the gh login lookup gives `GH_CONFIG_DIR` through `CONST_GH_LOGIN_ENV_VARS`.

## Existing Tool Considered

The default `env_delete` table of sudo is the maintained, open list of environment keys that change the code that a program runs. It lists no key of gh or kubectl. No library publishes a list for import, so the constant names the source of each key, as #2205, #2429, #2483 and #2633 decided. The match keeps `fnmatch.fnmatchcase` of the standard library. The change builds no new code path: it adds seven names to the existing tuple. Written cost: about 1500 tokens to build, keep and fix it, and under one hour elapsed.
