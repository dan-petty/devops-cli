# Proposal: the GitHub token reaches only the git and gh calls that need it

## Why

This change answers a private security advisory of the repository. The process runner gave the GitHub token of the session to each git child, also to a git child that reaches no remote (`git add`, `git commit`, `git diff`). The implement job ran its network git calls (`push`, `fetch`, `ls-remote`) in the clone, with the home folder of the pod. Such a call reads the git configuration files of that home folder and of the clone, the hooks of the clone and the attribute files of the checkout. The shell of the agent runs as the same user, so it can write each of these files. A program that one of these files names starts as a child of git, with the token in its environment.

The process runner also gave the token to each gh child as `GH_TOKEN`. gh gives its environment to each `--jq` filter (go-gh `pkg/jq`, `gojq.WithEnvironLoader`), and the caller writes the filter. `mask_secrets` finds a token only by its prefix, so a part of the token can reach the output.

The invariants of this change: no git call that holds the token reads a configuration, hook, attribute or credential file that the agent can write, and no process that the agent or a git call without the token started is alive when a git call with the token starts. No token is in the environment of a gh child, whose output a caller can shape.

## What Changes

- The process runner gives the session's token only to a git child that reaches a remote: `push`, `fetch`, `pull`, `ls-remote`, `clone`, and `remote set-head`, `remote show`, `remote update` and `remote prune`. It reads the subcommand after the global options of git (`-C`, `-c`, `--git-dir` and the others that take a value). Any other git child gets no `GH_TOKEN` and no `GITHUB_TOKEN`, and starts no token lookup.
- The process runner gives a gh child no `GH_TOKEN` and no `GITHUB_TOKEN`. For each gh child it makes a new folder with mode 0700 under `$XDG_RUNTIME_DIR/gh-config`, or under `<data directory>/gh-config` when there is no runtime folder (the root file system of a runner Job is read-only), writes the token to `hosts.yml` (mode 0600) and `version: "1"` to `config.yml`, and sets `GH_CONFIG_DIR` to the folder and `GH_HOST=github.com`. It removes the folder when the child ends, also after a failure or a timeout. The local gh commands (`gh auth`, version and help) get the tokens of the environment as before.
- `build_subprocess_env` accepts two git keys from a caller, each with one fixed value only: `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1`. Each turns a configuration file off and names no program and no file. Any other value of these keys stays refused.
- A new module `roadmap/implement/git_isolation.py` runs each network git call of the implement job (`OriginGit`):
  1. It checks the git settings of the clone (below).
  2. It ends every leftover process of the job (`end_leftover_processes`), so that no process of the agent, and no program that the git calls of the check started, sees the new folder.
  3. It makes a new folder with `tempfile.mkdtemp`, and in it a new bare git folder whose `objects` folder is a link to the object folder of the clone, and an empty home folder. It copies the remote-tracking refs of the clone into the new git folder, so that a fetch sends only the objects that the clone lacks. These calls get no token.
  4. It ends every leftover process again.
  5. It runs the git call with the token in the new git folder: `git --git-dir=<new> -c credential.helper= -c credential.https://github.com.helper= -c 'credential.https://github.com.helper=!gh auth git-credential' -c core.hooksPath=/dev/null -c gc.auto=0 -c maintenance.auto=false`, with `--no-verify` for a push, and the environment `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_TERMINAL_PROMPT=0`, `HOME` and `GH_CONFIG_DIR` set to the empty home folder. The remote is the URL of `origin` that the job read before its first step, never the configuration of the clone at the time of the call.
  6. It writes the remote-tracking ref that the call changed into the clone with `git update-ref`, with no token, and removes the folder.
- The job checks the git settings of the checkout when each turn of the agent ends and before each network git call. The check reads the configuration of the scopes `local` and `worktree` (`git config --list --show-scope`), the attributes `filter`, `diff` and `merge` of each path that git would stage (`git check-attr`), and the file `objects/info/alternates` of the clone. A key outside a small allowlist, a filter, a diff or merge driver that git does not define itself, or an alternates file stops the item with the new failure class `git_config`, whose default action is `wait`. The reason and the log line name the key or the attribute and the path, and never a value.
- `add_worktree` takes an optional `origin` that reads the branches of `origin` and fetches. The job passes its `OriginGit`, so the worktree of a second item of one run is also made with the network calls above. A person who runs `devops repos worktrees add` gets the git commands as before.
- A push of the job sends a commit, not a branch name (`<sha>:refs/heads/<branch>`), and sets no upstream. The job reads the remote-tracking ref of the branch, which the push writes.
- SECURITY.md says that `mask_secrets` is a last net and no boundary: no secret goes into the environment of a process whose output a caller shapes.
- SECURITY.md, docs/ROADMAP_WORKFLOW.md and the text of `process_hardening.py` and `implement_run.py` describe the invariant.

## Capabilities

- `subprocess-environment` (modified): the two fixed git keys reach the child; only a git child that reaches a remote gets the token; a gh child reads the token from a private configuration folder.
- `github-app-identity` (modified): a gh child gets the App's token in its private configuration folder, and a git child only when it reaches a remote.
- `roadmap-failure-taxonomy` (modified): the class `git_config` with the action `wait`.
- `roadmap-implement-runner` (modified): the network git calls of the implement job and the check of the git settings.

## Impact

- A local git command of devops-cli, on a workstation too, starts with no token and no lookup of one. The network git commands get the token as before.
- A gh child of devops-cli reads no configuration of the person (aliases, the pager, the editor) and no login of the keyring: it reads the session's token from its own folder. `GH_HOST` makes it address github.com, the only host of the token. A process that is killed while a gh child runs can leave the folder of that call; it holds a token that the next run does not read.
- Each network git call of the implement job makes 4 more git calls with no token (an init, a read and a write of refs, and an update of one ref) and two sweeps of leftover processes. The objects stay in the clone, so the new folder holds only refs. A background process of the agent ends at the next push of a `wip:` commit, not only at the end of the turn.
- A target repository whose attributes name a filter, or a diff or merge driver that git does not define, stops at the first turn with `git_config`. No repository of the roadmap has one today.
- This change fits one pull request.

## Feasibility

- `src/devops_cli/core/process.py` `_pin_github_token` gave `GH_TOKEN` to each child whose program is `git`, whatever its subcommand. `src/devops_cli/roadmap/implement/implement_run.py` ran `git add -A` and `git commit` through the process runner (`_commit_if_changed`), and `push`, `fetch` and `ls-remote` in the worktree (`_publish`, `_push_with_lease`, `_withdraw`, `_sync`, `_rebased_copy`, `_base`). `implement_step.py` runs `git add -A` in `_stage`, and the keeper of `implement_wip.py` pushes a `wip:` commit from inside a turn of the agent (`log.before_request`), before `end_leftover_processes` runs at the end of the turn.
- `k8s/devops/cronjob-runner.yaml` mounts the volume `home` at `/home/devops`, and the `Dockerfile` sets `HOME=/home/devops` and the system helper `credential.https://github.com.helper=!gh auth git-credential`. The root file system of the Job is read-only, so `/etc/gitconfig` and the folders of `PATH` are not writable.
- git 2.55.0 on 2026-11-12, in a scratch repository: an empty value of `credential.helper` or `credential.https://github.com.helper` given with `-c` clears each helper that a configuration file set before it, and the helper after it runs. `git --git-dir=<new> push <origin> <sha>:refs/heads/feat`, with `objects` a link to the object folder of the source, sent the commit, and the trace shows no process that reads the source repository. A fetch in the same folder wrote the new objects into the object folder of the source. `git config --list --show-scope -z` names the scope of each key, and gives the keys of a file that `include.path` names under the scope of the file that includes it.
- A full local fetch of `main` of this repository into an empty bare repository took 15 s and 37 MB (27 s of CPU), so the new git folder links the objects of the clone and copies no object.
- go-gh `pkg/jq/jq.go` compiles a filter with `gojq.WithEnvironLoader(os.Environ)`, and `uv run devops gh api rate_limit --jq '[(env.GH_TOKEN|length), (env.GH_TOKEN[4:]|length)]'` printed `[40,36]` before this change. gh reads `oauth_token` of `hosts.yml` in `GH_CONFIG_DIR` when the environment has no token (go-gh `pkg/auth` `TokenFromEnvOrConfig`), and skips the move of its configuration when `config.yml` holds `version: "1"`. The live checks after this change are in the pull request.
- `gh auth git-credential` reads `GH_TOKEN` for `github.com` (#5162, `infra/repo_tree.py`). The project rules do not let an agent run a bare `gh`, so the empty `GH_CONFIG_DIR` was not tried with `gh` itself. The tests check the helper in the command line, and a real Job run checks it.

## Existing Tool Considered

gh's own configuration folder (`GH_CONFIG_DIR`, `hosts.yml`) carries the token of a gh child; a `--jq` filter run by devops-cli with a jq library in a child with an empty environment would replace a gh option with our own code. git covers each part of the git calls: the configuration environment of git (`GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM`, `-c`), a bare git folder with a linked object folder, `git update-ref --stdin`, `git config --list --show-scope` and `git check-attr`. `tempfile.mkdtemp` makes the folder, and `psutil` (through `end_leftover_processes`) ends the processes. The two-container Job of #3700 is the structural fix: the token would stay in a container that the agent cannot reach. It needs a change of the admission policy and is larger. This change is the fix in the pod. The new module is glue around these tools: about 0.5M tokens to build, 0.05M tokens a quarter to keep and fix, and one day. The change deletes `JobRun._refspec` and the `-u` of the first push.
