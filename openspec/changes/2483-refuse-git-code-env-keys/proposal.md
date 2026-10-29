# Proposal

## Why

Issue #2483: the subprocess environment guard accepts the git keys that make a git child run a program that its caller did not choose.

- `build_subprocess_env` in `src/devops_cli/core/process.py` refuses a caller override that `CONST_CODE_LOADING_ENV_PATTERNS` matches: the loader, gconv, bash, zsh and interpreter keys (#2205, #2433, #2429). It has no git key.
- A caller override of `GIT_CONFIG_COUNT` with `GIT_CONFIG_KEY_<n>` and `GIT_CONFIG_VALUE_<n>` gives git a configuration value. A value such as `core.fsmonitor`, `core.sshCommand`, `core.pager` or an alias that starts with `!` runs a program. `GIT_CONFIG_PARAMETERS`, which `git -c` sets, does the same.
- `GIT_SSH_COMMAND` and `GIT_SSH` name the program that git starts for an SSH remote. `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_SYSTEM` name a configuration file. `GIT_EXEC_PATH` names the directory of the git sub-programs. `GIT_ASKPASS`, `GIT_EDITOR`, `GIT_SEQUENCE_EDITOR`, `GIT_PAGER`, `GIT_EXTERNAL_DIFF` and `GIT_PROXY_COMMAND` name a program. `GIT_TEMPLATE_DIR` names a directory whose hooks git copies into a new repository. `EDITOR`, `VISUAL` and `PAGER` are the fall-back keys of the editor and the pager of git.
- `DEFAULT_ALLOWED_ENV_VARS` lets the ambient `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`, `GIT_EXEC_PATH`, `EDITOR` and `PAGER` reach an isolated child.
- devops-cli gives git the override `GIT_SSH_COMMAND=ssh -o BatchMode=yes` itself, in `render_at_revision` of `src/devops_cli/k8s/argocd_overrides.py`, as a caller override of `build_subprocess_env`. A guard that refuses `GIT_SSH_COMMAND` stops that fetch, so the change moves the option out of the environment.

## What Changes

- `CONST_CODE_LOADING_ENV_PATTERNS` in `src/devops_cli/config/constants.py` adds the git group of the design, in its own block with the manual page of each key. A caller override of one of these keys raises the same `SecurityError` as the other refused keys, with isolation on and off. The keys that git documents and that run no program stay accepted: `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL`, `GIT_TERMINAL_PROMPT`, `GIT_CONFIG_NOSYSTEM` and `GIT_SSH_VARIANT`.
- `DEFAULT_ALLOWED_ENV_VARS` in `src/devops_cli/core/process.py` removes `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`, `GIT_EXEC_PATH`, `EDITOR` and `PAGER`. Thus no key that the guard refuses reaches an isolated child from the environment of the person.
- `render_at_revision` gives `git fetch` the option `-c core.sshCommand=ssh -o BatchMode=yes` in its argument list, and `CONST_GIT_NONINTERACTIVE_ENV` keeps only `GIT_TERMINAL_PROMPT=0`. The option has the same effect as the old override, and no environment key carries it.
- The three `git config --global` calls (`configure_git_signing` of `src/devops_cli/crypto/ssh_keys.py` and the two git defaults of `src/devops_cli/commands/devcontainer.py`) name `GIT_CONFIG_GLOBAL` in `extra_allowed_env`, so that they write the file that `git config --global` writes in the shell of the person.
- The child environment bullet of `ARCHITECTURE.md` and the purpose of the `subprocess-environment` spec name the git keys as refused keys, and no longer as keys that reach the child.
- The refusal and the isolated environment are what a consumer sees, so the change adds requirements to the `subprocess-environment` spec.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `subprocess-environment`: the refused caller overrides add the git keys that make git run a program, and an isolated child gets none of them from the environment unless the caller names it. The change adds requirements and rewrites no existing requirement.

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/core/process.py`, `src/devops_cli/k8s/argocd_overrides.py`, `src/devops_cli/crypto/ssh_keys.py`, `src/devops_cli/commands/devcontainer.py`.
- Tests: `tests/test_subprocess_env_boundary.py`, `tests/test_k8s_argocd_overrides.py`, `tests/test_devcontainer.py`.
- Documents: `ARCHITECTURE.md`, and the purpose of `openspec/specs/subprocess-environment/spec.md`.

## Feasibility

- The guard accepts the keys today. On `origin/main` at `a3eb41f4`, the command of step 1 of the issue printed `['GIT_CONFIG_COUNT', 'GIT_CONFIG_KEY_0', 'GIT_CONFIG_VALUE_0', 'GIT_SSH_COMMAND']` with no `SecurityError`. `DEFAULT_ALLOWED_ENV_VARS` holds `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`, `GIT_EXEC_PATH`, `EDITOR` and `PAGER`.
- Step 3 of the issue, with git 2.55.0 and `env -i PATH=/usr/bin:/bin HOME=<dir>`, printed `GIT-CONFIG-FSMONITOR-RAN`. A `GIT_CONFIG_GLOBAL` file with `core.fsmonitor` printed `GIT-CONFIG-GLOBAL-RAN`.
- Each probe below ran in a temporary directory with the same `env -i` environment, a repository made with `git init`, and a key whose value prints a marker. Each printed its marker, so git ran the program:
  - `GIT_CONFIG_SYSTEM` with a file that sets `core.fsmonitor`, and `GIT_CONFIG_PARAMETERS='core.fsmonitor=...'`, with `git status`.
  - `GIT_SSH_COMMAND`, and `GIT_SSH` with an executable file, with `git ls-remote ssh://host.invalid/x`.
  - `GIT_PROXY_COMMAND` with `git ls-remote git://host.invalid/x`.
  - `GIT_EXEC_PATH` with a directory that holds `git-frobnicate` (`git frobnicate`) and `git-remote-https` (`git ls-remote https://example.invalid/x`).
  - `GIT_ASKPASS` with `git credential fill`.
  - `GIT_EDITOR`, `EDITOR` and `VISUAL` (with `TERM=xterm`) with `git commit --allow-empty`, and `GIT_SEQUENCE_EDITOR` with `git rebase -i --root`.
  - `GIT_EXTERNAL_DIFF` with `git diff`.
  - `GIT_TEMPLATE_DIR` with a `hooks/post-checkout` file, with `git clone`.
  - `GIT_PAGER` and `PAGER` with `git log -1` on a pseudo-terminal that `script(1)` made.
- With `GIT_CONFIG_NOSYSTEM=1`, git did not read the `GIT_CONFIG_SYSTEM` file, so that key runs no program. The `git(1)` page lists `GIT_AUTHOR_*`, `GIT_COMMITTER_*`, `GIT_TERMINAL_PROMPT` and `GIT_SSH_VARIANT` with no program.
- The manual pages of git 2.55.0 list the keys: `git(1)`, `git-config(1)`, `git-init(1)` and `git-var(1)`. No page lists `GIT_CONFIG_PARAMETERS`: it is the variable that `git -c` uses for the child processes of git, and the probe shows its effect.
- The default `env_delete` table of sudo (`initial_badenv_table` in `plugins/sudoers/env.c`, branch `main`) lists `GIT_SSH_COMMAND` and `GIT_CONFIG_*`. Commit `40217ea5` of 2026-03-28 added `GIT_SSH_COMMAND` and `GIT_CONFIG_GLOBAL`, and `main` now lists the whole `GIT_CONFIG_*` family.
- The path of the own override: `_stdout` of `src/devops_cli/k8s/argocd_overrides.py` calls the runner of `render_at_revision`, that is `_run_cmd` of `src/devops_cli/commands/k8s/cluster_runtime.py`, with `env=dict(CONST_GIT_NONINTERACTIVE_ENV)`. `_run_cmd` calls `run_subprocess`, and `run_subprocess` calls `build_subprocess_env(env=...)`. It is a caller override. It is the only use of `CONST_GIT_NONINTERACTIVE_ENV`. The other callers that set a git key give only `GIT_TERMINAL_PROMPT=0` (`roadmap/refine.py`, `roadmap/refine_investigation.py`, `ai/review/samples.py`).
- `git -c core.sshCommand='ssh -o BatchMode=yes' fetch ssh://git@example.com/x.git main` started `ssh` with `-o BatchMode=yes`, as `GIT_SSH_COMMAND='ssh -o BatchMode=yes'` does. A stand-in `ssh` file on `PATH` recorded the arguments of both.
- No file in `src/` sets or reads `EDITOR`, `VISUAL` or `PAGER` for a child. No test sets one. The ambient `GIT_CONFIG_GLOBAL` has two readers: the three `git config --global` calls, and the `global_git_config` fixture of `tests/test_ssh.py`, which redirects them to a file below `tmp_path`.

## Existing Tool Considered

The default `env_delete` table of sudo is the maintained, open list of environment keys that change the code that a program runs. It names two of the git keys. The `git(1)`, `git-config(1)`, `git-init(1)` and `git-var(1)` pages name the others, and the probes confirm each one. No library publishes the list for import, so the constant copies the keys and names the sources, as #2205 and #2429 decided. The match keeps `fnmatch.fnmatchcase` of the standard library. The SSH option moves to `git -c`, the option that git gives for this need, so the change builds no pin step and no bypass. The change deletes the five keys from the ambient allowlist and the SSH key from `CONST_GIT_NONINTERACTIVE_ENV`.
