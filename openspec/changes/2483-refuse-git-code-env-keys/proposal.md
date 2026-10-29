# Proposal

## Why

Issue #2483: the subprocess environment guard accepts git keys that make a git child run a program that its caller did not choose.

- `build_subprocess_env` in `src/devops_cli/core/process.py` refuses a caller override that `CONST_CODE_LOADING_ENV_PATTERNS` matches. The patterns hold the loader, gconv, bash, zsh and interpreter keys (#2205, #2433, #2429). They hold no git key.
- `GIT_CONFIG_COUNT` with `GIT_CONFIG_KEY_<n>` and `GIT_CONFIG_VALUE_<n>` gives git a configuration value. A value such as `core.fsmonitor`, `core.sshCommand` or an alias that starts with `!` runs a program.
- Many other git keys run a program. `GIT_SSH_COMMAND`, `GIT_ASKPASS` and `GIT_EDITOR` name one. `GIT_EXEC_PATH` and `GIT_TEMPLATE_DIR` name a directory of programs or hooks. `GIT_CONFIG_GLOBAL` names a configuration file.
- A review found keys that a list of names misses: `GIT_TEST_FSMONITOR`, `GIT_TEST_MAINT_SCHEDULER`, `GIT_ALLOW_PROTOCOL`, `GIT_DIFFTOOL_EXTCMD` and `MERGE_TOOLS_DIR`. A list stays incomplete when git adds a key.
- `EDITOR`, `VISUAL` and `PAGER` are the keys that git uses when its own keys are not set. `LESSOPEN` makes `less`, the pager of git, run a program.
- `DEFAULT_ALLOWED_ENV_VARS` lets the ambient `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`, `GIT_EXEC_PATH`, `EDITOR` and `PAGER` reach an isolated child.
- devops-cli gives git the override `GIT_SSH_COMMAND=ssh -o BatchMode=yes` in `render_at_revision`. It is a caller override, so a guard that refuses the key stops that fetch.

## What Changes

- The guard refuses each `GIT_` key of a caller, but five keys that devops-cli callers set and that run no program. The five are `GIT_TERMINAL_PROMPT`, `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME` and `GIT_COMMITTER_EMAIL`. A key that git adds later stays refused until a person reviews it.
- The guard also refuses `EDITOR`, `VISUAL`, `PAGER`, `LESSOPEN`, `LESSCLOSE` and `MERGE_TOOLS_DIR`. Each raises the same `SecurityError` as the other refused keys, with isolation on and off.
- `DEFAULT_ALLOWED_ENV_VARS` removes `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`, `GIT_EXEC_PATH`, `EDITOR` and `PAGER`. Thus no refused key reaches an isolated child from the environment.
- `render_at_revision` gives `git fetch` the option `-c core.sshCommand=ssh -o BatchMode=yes`. `CONST_GIT_NONINTERACTIVE_ENV` keeps only `GIT_TERMINAL_PROMPT=0`.
- This replaces criterion 3 of the issue. The issue asked for a post-guard step that gives the child `GIT_SSH_COMMAND`. The design says why the argument is better.
- The three `git config --global` calls name `GIT_CONFIG_GLOBAL` in `extra_allowed_env`. They write the file that the person set.
- `ARCHITECTURE.md` and the purpose of the `subprocess-environment` spec name the git keys as refused keys.
- The refusal and the isolated environment are what a consumer sees, so the change adds requirements to the `subprocess-environment` spec.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `subprocess-environment`: the guard refuses the git keys that devops-cli does not set, and an isolated child gets none of them from the environment. The change adds requirements and rewrites no existing requirement.

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/core/process.py`, `src/devops_cli/k8s/argocd_overrides.py`, `src/devops_cli/crypto/ssh_keys.py`, `src/devops_cli/commands/devcontainer.py`.
- Tests: `tests/test_subprocess_env_boundary.py`, `tests/test_k8s_argocd_overrides.py`, `tests/test_devcontainer.py`.
- Documents: `ARCHITECTURE.md`, and the purpose of `openspec/specs/subprocess-environment/spec.md`.

## Feasibility

- The guard accepts the keys today. On `origin/main` at `a3eb41f4`, the command of step 1 of the issue printed `['GIT_CONFIG_COUNT', 'GIT_CONFIG_KEY_0', 'GIT_CONFIG_VALUE_0', 'GIT_SSH_COMMAND']` with no `SecurityError`. `DEFAULT_ALLOWED_ENV_VARS` holds `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`, `GIT_EXEC_PATH`, `EDITOR` and `PAGER`.
- Step 3 of the issue, with git 2.55.0 and `env -i PATH=/usr/bin:/bin HOME=<dir>`, printed `GIT-CONFIG-FSMONITOR-RAN`. A `GIT_CONFIG_GLOBAL` file with `core.fsmonitor` printed `GIT-CONFIG-GLOBAL-RAN`.
- Each probe below ran in a temporary directory, with the same `env -i` environment and a temporary `HOME`. It used a repository made with `git init` and a key whose value prints a marker. Each printed its marker, so the program ran.
  - Configuration: `GIT_CONFIG_SYSTEM` with a file that sets `core.fsmonitor`, and `GIT_CONFIG_PARAMETERS='core.fsmonitor=...'`, with `git status`.
  - Programs: `GIT_SSH_COMMAND` and `GIT_SSH` with `git ls-remote ssh://host.invalid/x`, and `GIT_PROXY_COMMAND` with `git ls-remote git://host.invalid/x`.
  - Programs: `GIT_ASKPASS` with `git credential fill`, and `GIT_EXTERNAL_DIFF` with `git diff`.
  - Editors: `GIT_EDITOR`, `EDITOR` and `VISUAL` (with `TERM=xterm`) with `git commit --allow-empty`, and `GIT_SEQUENCE_EDITOR` with `git rebase -i --root`.
  - Pagers: `GIT_PAGER` and `PAGER` with `git log -1` on a pseudo-terminal that `script(1)` made. `LESSOPEN="|<program> %s"` and `LESSCLOSE` ran with `less <file>` on the same pseudo-terminal.
  - Directories: `GIT_EXEC_PATH` with a directory that holds `git-frobnicate` and `git-remote-https`, and `GIT_TEMPLATE_DIR` with a `hooks/post-checkout` file, with `git clone`.
  - Keys that only the source of git names: `GIT_TEST_FSMONITOR` with `git status`, and `GIT_TEST_MAINT_SCHEDULER=crontab:<program>` with `git maintenance start`.
  - Keys of the scripts of git: `GIT_DIFFTOOL_EXTCMD` with `git difftool -y HEAD`, and `MERGE_TOOLS_DIR` (a shell file) with `git difftool -y -t <tool> HEAD`.
  - Protocol: `GIT_ALLOW_PROTOCOL=ext` with `git ls-remote 'ext::<program>'`. Without the key, git did not run the program.
- The source of git reads `GIT_TEST_FSMONITOR` in `fsmonitor-settings.c` and `GIT_TEST_MAINT_SCHEDULER` in `builtin/gc.c`. The scripts `git-difftool--helper` and `git-mergetool--lib` read `GIT_DIFFTOOL_EXTCMD` and `MERGE_TOOLS_DIR`.
- With `GIT_CONFIG_NOSYSTEM=1`, git did not read the `GIT_CONFIG_SYSTEM` file. The pages `git(1)`, `git-config(1)`, `git-init(1)`, `git-var(1)` and `less(1)` list the other keys. No page lists `GIT_CONFIG_PARAMETERS`: `git -c` uses it for child processes of git.
- The default `env_delete` table of sudo (`initial_badenv_table` in `plugins/sudoers/env.c`, branch `main`) lists `GIT_SSH_COMMAND` and `GIT_CONFIG_*`. Commit `40217ea5` of 2026-03-28 added `GIT_SSH_COMMAND` and `GIT_CONFIG_GLOBAL`, and `main` now lists the whole `GIT_CONFIG_*` family.
- The path of the own override: `_stdout` of `src/devops_cli/k8s/argocd_overrides.py` calls the runner of `render_at_revision` with `env=dict(CONST_GIT_NONINTERACTIVE_ENV)`. The runner is `_run_cmd` of `src/devops_cli/commands/k8s/cluster_runtime.py`. It calls `run_subprocess`, which calls `build_subprocess_env(env=...)`. It is the only use of `CONST_GIT_NONINTERACTIVE_ENV`.
- The callers that set a git key give only `GIT_TERMINAL_PROMPT=0` (`roadmap/refine.py`, `roadmap/refine_investigation.py`, `ai/review/samples.py`). A tool request in `tests/test_tool_executor_contract.py` sets the author and the committer. No other file of `src/` or `tests/` gives a `GIT_` key as a caller override.
- `git -c core.sshCommand='ssh -o BatchMode=yes' fetch ssh://git@example.com/x.git main` started `ssh` with `-o BatchMode=yes`, as `GIT_SSH_COMMAND='ssh -o BatchMode=yes'` does. A stand-in `ssh` file on `PATH` recorded the arguments of both.
- No file in `src/` sets or reads `EDITOR`, `VISUAL` or `PAGER` for a child, and no test sets one. The ambient `GIT_CONFIG_GLOBAL` has two readers: the three `git config --global` calls, and the `global_git_config` fixture of `tests/test_ssh.py`.
- `src/devops_cli/openspec/tool.py` sets `XDG_CONFIG_HOME` as a caller override, so the guard cannot refuse it. A probe with `XDG_CONFIG_HOME` and a `git/config` file that sets `core.fsmonitor` ran a program in `git status`.

## Existing Tool Considered

The default `env_delete` table of sudo is the maintained, open list of environment keys that change the code that a program runs. It names two of the git keys, and the pages and the source of git name the others. No library publishes a list for import, so the constant names the sources, as #2205 and #2429 decided. The match keeps `fnmatch.fnmatchcase` of the standard library. The SSH option moves to `git -c`, the option that git gives for this need. Thus the change builds no pin step and no bypass, and it deletes five keys from the ambient allowlist.
