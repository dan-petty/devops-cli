# Proposal

## Why

Issue #2008: the stack names of the k8s commands are written in more than one place, so a new stack can be left out of `all` or out of a help text. The cluster Secret push table cannot build a value from other values of the same push, and every pushed Secret has the type `Opaque`. The Mattermost database Secret of #1391 needs both features: it is of type `kubernetes.io/basic-auth`, and its connection string is built from its user and password. The alert and deploy hooks of #1392 and #1393 are URLs built from the in-cluster Mattermost address and a hook ID in the keyring.

## What Changes

- `config/constants.py` declares the stack names once, in deploy order, as `CONST_K8S_STACKS`. `CONST_K8S_ALL_STACKS` is `all`, and `CONST_K8S_VALID_STACKS` is the stacks followed by `all`.
- `_resolve_stacks` takes `all` and the valid names from those constants and holds no stack literal. `stack_lifecycle.py` keeps no `VALID_STACKS` of its own. The k8s package exports the one in `networking.py`.
- Every help text that lists stacks takes them from the constants: the `--stack` help of the stack commands (`HELP.k8s.stack`), the deploy-stack summary, the `--stack` help of `push-secrets` and the `--stack` help of `devops devcontainer bootstrap-k8s`. deploy-stack is registered with `HELP.k8s.deploy_stack`, which nothing used before, and that summary now names every stack instead of "infrastructure or LLM".
- The push table gets a fourth source, `DerivedSource`. It is a URL template whose fields are other sources. The push resolves every other entry first. It then fills each field with its source's value, quoted with `urllib.parse.quote(..., safe="")`. A derived value is compared with the live value as any other value is. It is never adopted, generated or stored in the keyring. `--plan` and the output name its source as `derived from <sources>`, and `--dry-run` shows a placeholder.
- A table row may name its Secret type. The default is `Opaque`. The pushed manifest and the dry run's manifest carry the type of the row.
- `CONST_K8S_MATTERMOST_URL` holds the in-cluster base URL `http://mattermost.mattermost.svc.cluster.local:8065`, for the rows of #1391, #1392 and #1393.
- No manifest under `k8s/` changes, and the table gets no new row.
- The help texts and the push behavior are observable, so the change carries deltas in `k8s-stack-help` and `stack-credential-sync`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `k8s-stack-help`: one declaration of the stack names feeds `_resolve_stacks` and every help text that lists stacks.
- `stack-credential-sync`: the push writes derived entries and the Secret type of each row.

## Impact

- `src/devops_cli/config/constants.py`, `src/devops_cli/commands/k8s/networking.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`, `src/devops_cli/commands/k8s/__init__.py`, `src/devops_cli/commands/k8s/cluster_secret_push.py`, `src/devops_cli/lang/en/help.py`.
- `src/devops_cli/k8s/cluster_secrets.py`, `src/devops_cli/k8s/secret_push.py`.
- `tests/test_k8s_push_secrets.py`, `tests/test_k8s_networking.py`, `tests/test_k8s_devops_stack.py`, `tests/test_k8s_logging_stack.py`.
- `k8s/README.md`. `devops docs generate --sync-readme` rewrites the generated command and MCP documents.

## Feasibility

Checked on `main` at a408dee1, which holds #2608.

- Done already, so dropped from this change:
  - #2157 and #2388 moved the tuple to `CONST_K8S_VALID_STACKS` in `config/constants.py`. `networking.py:66` and `stack_lifecycle.py:289` now bind to it, not to their own literals.
  - `HELP.k8s.stack` (`lang/en/help.py:412`) is built from that tuple.
  - The post-Helm table `_POST_HELM_BY_STACK` exists (`stack_lifecycle.py:280-283`).
- Still open:
  - `_resolve_stacks` (`networking.py:69-79`) repeats the five names as literals.
  - `stack_lifecycle.py:289` keeps a second `VALID_STACKS`, which nothing in the module reads.
  - `HELP.k8s.deploy_stack` (`help.py:330`) says "infra, llm, all", and no command reads it. deploy-stack's summary is its docstring, "Deploy infrastructure or LLM stack".
  - `HELP.k8s.push_stack` (`help.py:336-338`) lists the stacks as literals.
  - `HELP.devcontainer.stack` (`help.py:809`) names `monitoring`, which is not a stack.
- Where the one tuple lives: the issue names `networking.py`. `lang/en/help.py` builds the help texts from the tuple, and `networking.py` imports `HELP`. A tuple in `networking.py` would make an import cycle, so the tuple stays in `config/constants.py`. The refinement of the issue proposes the same place.
- `secret_push.py:480` writes `"type": "Opaque"` for every Secret. `cluster_secrets.py` has three sources, `KeyringSource`, `SettingSource` and `LiteralSource`, and none of them builds a value from another.
- `_Sources.plan_store` already lets a later entry read a value that the push adopts or generates as the keyring's own value. A derived entry that is resolved after every other entry therefore sees the password that #1391's row adopts or generates.
- Kubernetes (`pkg/apis/core/validation/validation.go`, `ValidateSecret`): a Secret of type `kubernetes.io/basic-auth` must hold `username` or `password` and may hold other keys. The `type` of a Secret cannot change after it is created, so a row names its type before its first push.
- Python 3.14.10 (the project needs 3.14 or later): `urllib.parse.quote(value, safe="")` quotes `/`, `:`, `@`, `?`, `#` and `%`, so a credential in the user-info part of a URL keeps its characters. `urllib.parse.urlsplit` and `unquote` give the user and password back unchanged (checked with a user `mat/ter:m@st` and a password `p@ss:w/rd?#%`).

## Existing Tool Considered

The Kubernetes Secret `type` field and its built-in type `kubernetes.io/basic-auth` carry the Secret type. Python's `str.format` and `urllib.parse.quote` build and quote a derived value. No library is added. The push keeps its own planner, because no open tool writes Secrets from the OS keyring with this adopt, generate and rotate behavior: the table and the planner came with #741. The change deletes the stack literals of `_resolve_stacks`, the second `VALID_STACKS` in `stack_lifecycle.py`, the stack literals of three help texts and the hard-coded `Opaque` type.
