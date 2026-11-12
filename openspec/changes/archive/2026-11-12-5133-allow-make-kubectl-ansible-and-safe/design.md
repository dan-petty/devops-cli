# Design

## Decisions

- The rules go in the committed `.claude/settings.json` of this repository. A session that starts here reads this file, and a rule matches the full command line in each directory, so the rules also cover the homelab clone under `repos/`.
- The template of `devops devcontainer init` stays equal to the committed file. A test requires it, and a scaffolded repository gets the same agent setup as this one.
- The list allows the local git writes `worktree`, `add`, `commit` and `rebase`, and no command that AGENTS.md limits: `git push`, `git reset`, `git checkout`, `git switch` and `git stash`. The classifier continues to examine them.
- The deny list does not change. The owner keeps agent permissions permissive and wants no new deny list.

## Rejected alternatives

- A narrow rule for each target, such as `Bash(make design-tokens)`. The homelab Makefile has many host targets, and `ANSIBLE_ARGS` changes on each run. A narrow rule does not match `make k3s ANSIBLE_ARGS="--limit <node>"`.
- `kubectl` only in `settings.local.json`. The file is personal and git ignores it, so a new clone, a cloud session and a scaffolded repository do not get the rule.
- A template with a shorter list than the committed file. The test that keeps the two files equal would need an exception, and the scaffold would not give the setup of this repository.
- A deny rule for `git commit -n`, the short form of `--no-verify`. The owner wants no new deny list. The pre-push hook still runs the static checks before each push.
