# Proposal: #5133

## Why

The committed `.claude/settings.json` allows only `uv run devops`, `uv run pytest`, `openspec`, `tuicr` and four git reads. The auto-mode classifier examines each other command, and it can refuse one. On 2026-11-12 it refused `make k3s` in the homelab clone under `repos/`, because no rule covers `make`. `kubectl` is allowed only in a personal `settings.local.json`. The owner asked to add `make` and the other standard project commands to the settings of each repository. The homelab cluster is the development environment of the project, and agents have full access to it. Secrets and hardware stay with the owner. Closes #5133.

## What Changes

- `.claude/settings.json` and its template `src/devops_cli/templates/claude_settings.json.j2` allow `make`, `kubectl`, `ansible`, `ansible-playbook`, `ansible-inventory`, `ansible-lint`, `uv sync`, `uv lock`, the git reads `fetch`, `show`, `rev-parse` and `merge-base`, and the local git writes `worktree`, `add`, `commit` and `rebase`.
- The allow list does not include `git push`, `git reset`, `git checkout`, `git switch` or `git stash`. AGENTS.md limits them, so the classifier continues to examine them.
- The deny list does not change. A deny rule wins over an allow rule, so `--no-verify` and bare `gh` stay refused.
- CONTRIBUTING.md gives the allow list and says that `Bash(uv run devops *)` also covers the commands of the planned `infra` group (#5120).
- `devops devcontainer init` writes the template, so the change is observable and carries a delta of `devcontainer-agent-config`.

## Capabilities

- `devcontainer-agent-config`: ADDED "The Claude Code settings allow the standard project commands".

## Impact

An agent session in this repository, or in a clone under `repos/`, runs the listed commands with no classifier check. A repository that `devops devcontainer init` scaffolds gets the same list. The change fits one pull request. The homelab repository gets its own `.claude/settings.json` in a pull request in that repository.

## Feasibility

- The permissions page of Claude Code (https://code.claude.com/docs/en/permissions) says: "Rules are evaluated in order: deny, then ask, then allow." A trailing ` *` matches the bare command and requires a word boundary. Every subcommand of a compound command must match an allow rule or be a read-only command, and a `cd` into a working directory is read-only.
- The permission modes page says that auto mode drops "broad allow rules that grant arbitrary code execution" and that other allow rules resolve with no classifier check. In the Claude Code 2.1.322 binary, `isDangerousBashPermission` drops a rule only when it names a command of this list: the interpreters (`python`, `node`, `deno`, `tsx`, `ruby`, `perl`, `php`, `lua`), `npx`, `bunx`, `npm run`, `yarn run`, `pnpm run`, `bun run`, the shells, `ssh`, `eval`, `exec`, `env`, `xargs` and `sudo`. `make`, `kubectl`, `ansible*`, `uv` and `git` are not in it, so auto mode keeps the new rules.
- `tests/commands/test_devcontainer.py` already requires the template to equal the committed file.

## Existing Tool Considered

Claude Code permission rules. The change adds configuration only and builds no code. It deletes no internal code.
