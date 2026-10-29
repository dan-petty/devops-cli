# Design

## Decisions

- **The sources are the git manual pages and sudo.** sudo removes `GIT_SSH_COMMAND` and the `GIT_CONFIG_*` family before it runs a program for another user (`initial_badenv_table` of `plugins/sudoers/env.c`). The pages `git(1)`, `git-config(1)`, `git-init(1)` and `git-var(1)` name the other keys. A probe with git 2.55.0 confirms that each refused key makes git run a program (proposal, Feasibility).
- **The refused keys, with their sources.**

  | Group | Keys | Source |
  | :--- | :--- | :--- |
  | Configuration | `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_<n>`, `GIT_CONFIG_VALUE_<n>`, `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM` | `git-config(1)`, sudo, probe |
  | Configuration | `GIT_CONFIG_PARAMETERS` | `git(1)` option `-c`, probe |
  | Program | `GIT_SSH`, `GIT_SSH_COMMAND`, `GIT_ASKPASS`, `GIT_EDITOR`, `GIT_SEQUENCE_EDITOR`, `GIT_PAGER`, `GIT_EXTERNAL_DIFF`, `GIT_EXEC_PATH` | `git(1)`, sudo for `GIT_SSH_COMMAND`, probe |
  | Program | `GIT_PROXY_COMMAND` | `git-config(1)`, `core.gitProxy`, probe |
  | Directory | `GIT_TEMPLATE_DIR` | `git-init(1)`, probe |
  | Fall-back | `EDITOR`, `VISUAL`, `PAGER` | `git-var(1)`, probe |

- **Exact names, with a prefix only for the numbered keys.** The constant lists each key by its name, and `GIT_CONFIG_KEY_*` and `GIT_CONFIG_VALUE_*` for the pairs that `GIT_CONFIG_COUNT` counts. sudo refuses the whole `GIT_CONFIG_*` family. That family also holds `GIT_CONFIG_NOSYSTEM`, which makes git skip the system file and runs no program, and a caller can have a reason to set it. #2429 made the same choice for `PYTHONUNBUFFERED` and `NODE_ENV`. The test of the accepted overrides pins `GIT_CONFIG_NOSYSTEM`, `GIT_SSH_VARIANT`, `GIT_TERMINAL_PROMPT`, the author and committer keys, and two names that only contain a refused name.
- **A key that runs a program only in some runs is refused too.** `GIT_ASKPASS` runs only when git asks for a password. The editor keys run only for a commit message or a rebase list, and the pager keys only on a terminal. `GIT_EXEC_PATH` runs a program only for a git command that is not built in. A caller has no reason to set one of these keys, and the value is a program or the place of one, as #2429 decided for `PS4`, `FPATH` and `PYTHONSTARTUP`.
- **`EDITOR`, `VISUAL` and `PAGER` are refused with the git keys.** `git-var(1)` says that git uses `$VISUAL`, then `$EDITOR`, when `GIT_EDITOR` and `core.editor` are not set, and `$PAGER` when `GIT_PAGER` and `core.pager` are not set. The probe ran the program of each. A refusal of `GIT_EDITOR` alone leaves the other keys that name the same program. No file of `src/` sets or reads these keys for a child, and no test sets one.
- **No refused key reaches an isolated child from the environment.** `DEFAULT_ALLOWED_ENV_VARS` removes `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`, `GIT_EXEC_PATH`, `EDITOR` and `PAGER`. Then no allowed key or prefix matches a refused pattern, and the test of #2429 pins this with every refused key in the environment. This is the rule of the spec requirement "An isolated child gets no refused key from the environment", and #2429 removed `PYTHONPATH` and `PYTHONHOME` on the same ground. The default `env_reset` of sudo keeps neither `EDITOR` nor `PAGER` either. A person who wants an ambient value in a child keeps two paths: `isolate_env=False`, and the `extra_allowed_env` of a caller.
- **The own override moves to the argument list of git.** The path of the override is a caller override of `build_subprocess_env`: `render_at_revision` passes `CONST_GIT_NONINTERACTIVE_ENV` as `env` to the runner. After the change the fetch is `git -C <dir> -c core.sshCommand=ssh -o BatchMode=yes fetch ...`, and the environment holds only `GIT_TERMINAL_PROMPT=0`, a key that the guard accepts. `-c` is the option of git for a one-run configuration value, and it beats the configuration files. The guard keeps no exception, no flag and no list of trusted values, and the code that chooses the option is the code of devops-cli, not a caller of the guard. The option goes only to the fetch, the one command that opens an SSH connection, and not to `git init`, `git checkout` and `kubectl kustomize`, which the old override reached for no reason. With isolation on, an ambient `GIT_SSH_COMMAND` never reaches the child, so it cannot take precedence over `core.sshCommand`.
- **The `git config --global` calls name `GIT_CONFIG_GLOBAL`.** With the key out of the allowlist, `git config --global` writes `$HOME/.gitconfig`, and git of the person reads `GIT_CONFIG_GLOBAL` alone when it is set. The three calls (the signing keys of `ssh register` and `ssh rotate`, and the two defaults of `devcontainer post-start`) give `extra_allowed_env={"GIT_CONFIG_GLOBAL"}` through `CONST_GIT_GLOBAL_CONFIG_ENV`. The value is the one that the person set, as the design of #2429 says for `extra_allowed_keys`. The `global_git_config` fixture of `tests/test_ssh.py` keeps working with no change.
- **The constant keeps the length rule of #2433.** The comment above `CONST_CODE_LOADING_ENV_PATTERNS` stays at 25 words, and the change does not edit it. The git block adds one short comment above each group of keys, with the pages that name them, for example `# git-config(1)`. Each key has its source next to it. The block sits between the zsh keys and the Python keys, and the test list follows the same order, so a later change that appends a group at the end of the tuple (#2503) merges with no conflict.
- **The spec change only adds requirements.** The requirement "A caller override that loads code into the child is refused" names the loader and interpreter keys in its sentence and scenarios. A MODIFIED copy would conflict with #2503, which changes the same requirement. The new requirements add the git refusal, the accepted git keys, the SSH option of the fetch and the `git config --global` file. The purpose of the spec names the git child, and a delta cannot change a purpose, so the change edits the purpose line of `openspec/specs/subprocess-environment/spec.md` directly, as #2429 did.
- **The tests are in the behaviour file of the guard.** `tests/test_subprocess_env_boundary.py` takes the refused git keys in `REFUSED_OVERRIDE_KEYS`, so the existing tests of the override and of the ambient environment cover them. The fetch test is in `tests/test_k8s_argocd_overrides.py`, and the `git config --global` test is in `tests/test_devcontainer.py` and the existing `tests/test_ssh.py`.

## Rejected alternatives

- **Pin `GIT_SSH_COMMAND` after the guard, as `_pin_github_token` pins `GH_TOKEN`.** The pin works on the program name, so it reaches every git child, for example a release push, which #1124 runs with the environment of the person. It replaces the `core.sshCommand` of the person too. A pin that reaches one call needs a flag on `run_subprocess`, which is the bypass below.
- **Add a flag or a trusted-environment parameter to `build_subprocess_env`.** It weakens the guard for every caller, and a reviewer must audit each use of the flag.
- **Accept `GIT_SSH_COMMAND` when its value is the exact constant of devops-cli.** It keeps one path, but the guard then holds an exception that the next caller extends. The argument list needs none.
- **Check the value of `GIT_SSH_COMMAND`.** A new ssh option or another program name passes such a check, and the value is a shell command line.
- **Refuse the whole `GIT_CONFIG_*` family, as sudo does.** It refuses `GIT_CONFIG_NOSYSTEM`, which runs no program.
- **Refuse every `GIT_*` key that is not on a list.** It refuses `GIT_DIR`, `GIT_INDEX_FILE`, `GIT_WORK_TREE`, `GIT_TRACE` and the other keys that a caller has a reason to set. A new safe key of git then needs a review before it works. The probe shows which keys run a program, so the refusal lists them.
- **Keep `EDITOR` and `PAGER` in the allowlist and refuse them only as caller overrides.** A refused key then reaches an isolated child from the environment, which the spec requirement and its test forbid. No code needs the ambient keys.
- **Find the global configuration file in Python for the `git config --global` calls.** It copies the lookup that git does (`GIT_CONFIG_GLOBAL`, then `$XDG_CONFIG_HOME/git/config`, then `~/.gitconfig`). `extra_allowed_env` lets git do the lookup.

## Keys considered and accepted

- `GIT_DIR`, `GIT_WORK_TREE`, `GIT_COMMON_DIR`, `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY` and `GIT_ALTERNATE_OBJECT_DIRECTORIES` point git at a repository. Git runs a program only through the configuration of a repository that the caller chose, as it does for the `cwd` of the caller. Git hooks set these keys, and a caller that runs git inside a hook needs them.
- `GIT_CONFIG_NOSYSTEM`, `GIT_SSH_VARIANT`, `GIT_TERMINAL_PROMPT`, `GIT_AUTHOR_*` and `GIT_COMMITTER_*` run no program.
- `GIT_TRACE*` writes to a file that the caller names and runs no program.
- `HOME` makes git read `$HOME/.gitconfig`, which can set `core.fsmonitor`. It has the effect of the refused `GIT_CONFIG_GLOBAL`. The guard accepts it for the reason that #2429 gives: a caller must be able to give a child its own home directory.

## Non-goals

- The library keys that make a library of the child load a module, for example `OPENSSL_CONF`: #2503.
- The keys of `ssh` that name a program, `SSH_ASKPASS` and `SSH_ASKPASS_REQUIRE`: #2633. The keys of `gh` and `kubectl` that name a program, for example `GH_EDITOR` and `KUBE_EDITOR`: #2633 names them as candidates, and no probe of them ran.
